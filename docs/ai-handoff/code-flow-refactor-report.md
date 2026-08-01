# 申请链接代码顺序流程改造报告

> 历史说明：本文主体记录早期申请链接 Flow 改造。2026-08-01 的产品申请 P1/P2 边界与可靠性
> 收尾已替代其中 `EndpointExecutor`、Flow 持有 Job、Integration 直接持有
> `JobHttpCallObserver` 等旧描述；当前事实以 `p1-p2-reliability-closure-2026-08-01.md` 为准。

## 1. 基准与范围

- Repository：`hero233-li/Alkaid`
- Base branch：`main`
- Base commit：`a7a4f94e208d39ca2daf30bd60f1cd0ada124cae`
- Working branch：`agent/code-flow-refactor`
- 改造范围：仅申请链接纵向链路
- 数据库模型与迁移：无变更
- 前端：无变更

远程 `main` 是本次实现的唯一代码基准。本次没有使用或假定内网未推送的
`contexts/`、`flows/`、`tasks/`、`views/` 或 `product_system/` 目录。

## 2. 修改前真实调用链

```text
POST /api/product-data/tools/application-links/generate
  -> application_links.views.generate_application_link
     -> ApplicationLinkSubmission.model_validate_json
     -> normalize_submission
     -> resolve_execution_snapshot（内部同时校验）
     -> create_job（保存规范化 payload 和 snapshot）
     -> transaction.on_commit(enqueue_job)
  -> jobs.dispatch.enqueue_job
     -> application_links.tasks.execute_application_link.delay
  -> product_data/tasks.py 供 Celery autodiscover 导入 Task
  -> execute_application_link
     -> run_job_task
        -> Task 内部直接解析 submission
        -> 有 snapshot：反序列化 snapshot
        -> 无 snapshot：再次规范化并从当前 Catalog 解析 snapshot
        -> validate_submission
        -> generate_application_links（内部再次校验）
           -> ApplicationLinkAdapter
           -> EndpointExecutor
           -> HttpClient + JobHttpCallObserver
           -> mock transport 或真实外系统
        -> {"links": ApplicationLinkResult}
     -> run_job_task 标记 Job success/failed/timed_out/cancelled
```

修改前，Worker 端的业务步骤直接堆在 Celery Task 内；新 Job 的 Worker 路径校验两次，
旧 Job 的 Worker 路径校验三次。Job 生命周期和 HTTP 观察器本身已经完整，不需要重做。

## 3. 修改后真实调用链

```text
POST /api/product-data/tools/application-links/generate
  -> View：解析、规范化、解析 snapshot、显式校验、创建 Job
  -> transaction.on_commit(enqueue_job)
  -> execute_application_link Celery Task
  -> run_job_task
  -> ApplicationLinkFlow.execute
     -> create_context
     -> parse_submission
     -> load_execution_snapshot
     -> normalize_legacy_submission
     -> resolve_legacy_execution_snapshot
     -> validate_submission
     -> report_validation_completed
     -> generate_links
        -> generate_application_links
        -> ApplicationLinkAdapter
        -> EndpointExecutor
        -> HttpClient + JobHttpCallObserver
        -> mock transport 或真实外系统
     -> report_generation_completed
     -> ApplicationLinkResult
  -> Task 包装为 {"links": ...}
  -> run_job_task 保存 Job 成功结果或统一处理失败
```

执行顺序只由 `ApplicationLinkFlow.execute()` 中普通 Python 方法的排列决定。产品 JSON
继续只保存产品、路由和必填字段，不保存 `steps`、`next_step` 或执行顺序。旧 snapshot
中已有的可选 `handler` 字段仅由既有 Schema 兼容读取，不参与任何分派或方法调用；新 Job
不会写入该字段。

## 4. 文件变更清单

### 新增

- `Alkaid-python/apps/product_data/application_links/context.py`
- `Alkaid-python/apps/product_data/application_links/flow.py`
- `Alkaid-python/tests/test_application_link_flow.py`
- `docs/ai-handoff/code-flow-refactor-report.md`

### 修改

- `Alkaid-python/apps/product_data/application_links/tasks.py`
- `Alkaid-python/apps/product_data/application_links/services.py`
- `Alkaid-python/apps/product_data/application_links/views.py`
- `Alkaid-python/tests/test_runtime_mode.py`

### 删除

- 无

保留了 `Alkaid-python/apps/product_data/tasks.py`。没有创建
`product_data/tasks/`、全局 `contexts/`、全局 `flows/` 或其他菜单的空 Flow 文件。

## 5. 为什么采用 feature-local Flow

当前仓库已经按 `application_links/`、`business_access/`、`verification_approval/` 等业务功能
组织。申请链接是本次唯一需要改造的纵向链路，因此把 Context 和 Flow 放在
`application_links/` 内有以下效果：

- 调用方、Schema、Service、Task 与 Flow 位于同一业务边界；
- 不为其他菜单引入未使用的全局抽象；
- 不需要 Registry、Runner、反射或 JSON 步骤定义；
- 删除该功能时不会留下跨业务的空框架。

## 6. ApplicationLinkContext 字段

`ApplicationLinkContext` 是可变数据类，只保存本次流程实际共享的数据：

- `job`：当前 `Job`；
- `payload`：从 Job 复制的原始 payload；
- `submission`：解析后或旧 Job 规范化后的 `ApplicationLinkSubmission`；
- `execution_snapshot`：冻结 snapshot 或旧 Job 从当前 Catalog 解析出的 snapshot；
- `result`：`ApplicationLinkResult`。

Context 没有通用 `data` 字典，也没有步骤、当前位置、下一步、Handler 或工作流定义。

## 7. Task、Flow、Service、Adapter 职责

### Task

- 保留原 Celery task name、超时、`acks_late` 和 `reject_on_worker_lost`；
- 调用 `run_job_task`；
- 把 `JobTaskContext.progress` 作为回调交给 Flow；
- 把 `ApplicationLinkResult` 包装为既有 `{"links": ...}`；
- 失败时记录一份带 `job_id`、`workflow_id`、`trace_id`、`product`、`environment`、
  `category` 的结构化 traceback。

### Flow

- 明确排列 Worker 端业务步骤；
- 通过 Context 共享数据；
- 决定新旧 Job 的 snapshot 兼容顺序；
- 在业务边界校验一次；
- 调用现有 Service，不创建 HTTP 请求、不修改 Job 状态。

### Service

- 继续负责 submission 规范化、Catalog 路由解析、业务校验和结果生成；
- `resolve_execution_snapshot` 只解析 snapshot；
- `generate_application_links` 只执行已校验请求并生成业务结果；
- View 和 Flow 分别在自己的边界显式调用 `validate_submission`，消除隐藏的重复校验。

### Adapter

- 保持现有五字段表单、报文结构、mock/real 切换、Signer 门禁和响应模型；
- 继续复用 `EndpointExecutor`、`HttpClient` 和 `JobHttpCallObserver`；
- 未修改外系统协议、签名算法、路径或返回字段。

## 8. 旧 Job 与 snapshot 处理

### 已有 `execution_config_snapshot`

Flow 直接用 `ApplicationLinkExecutionSnapshot` 读取冻结配置，不重新读取 Catalog，也不再次
规范化 Job payload。随后校验 submission 与 snapshot 一致，再调用外系统。

### 没有 snapshot 的旧 Job

Flow 先按既有兼容逻辑规范化历史 payload 中的产品、环境和合作项目显示值，再从当前 Catalog
解析 snapshot，最后校验并执行。解析出的兼容 snapshot 仅用于本次执行，不修改数据库模型。

## 9. 数据库变更

没有修改任何 Model，没有新增或修改 migration。

验证：

```text
DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py makemigrations --check --dry-run
No changes detected
```

## 10. 测试命令与结果

执行环境使用仓库锁定依赖，但容器仅提供 Python 3.12.13；仓库正式要求 Python 3.10。

```text
DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py check
System check identified no issues (0 silenced).

DJANGO_SETTINGS_MODULE=config.settings.test CELERY_TASK_ALWAYS_EAGER=true \
  .venv/bin/python -m pytest tests/test_application_link_flow.py -q
5 passed

DJANGO_SETTINGS_MODULE=config.settings.test CELERY_TASK_ALWAYS_EAGER=true \
  .venv/bin/python -m pytest \
  tests/test_api.py \
  tests/test_application_link_integration.py \
  tests/test_jobs.py \
  tests/test_runtime_mode.py \
  tests/test_catalog_and_messages.py -q
35 passed

DJANGO_SETTINGS_MODULE=config.settings.test CELERY_TASK_ALWAYS_EAGER=true \
  .venv/bin/python -m pytest -q
63 passed

DJANGO_SETTINGS_MODULE=config.settings.test \
  .venv/bin/python scripts/compile_product_config.py --check
通过：version=7，products=3，agreement_messages=3

.venv/bin/python scripts/check_architecture.py
Architecture checks passed

.venv/bin/ruff check .
All checks passed

.venv/bin/ruff format --check \
  apps/product_data/application_links/context.py \
  apps/product_data/application_links/flow.py \
  apps/product_data/application_links/services.py \
  apps/product_data/application_links/tasks.py \
  apps/product_data/application_links/views.py \
  tests/test_application_link_flow.py \
  tests/test_runtime_mode.py
7 files already formatted
```

新增测试覆盖：

1. Task 委托给 `ApplicationLinkFlow` 并保持 `{"links": ...}`；
2. 使用冻结 snapshot；
3. 无 snapshot 的旧 Job 规范化与兼容解析；
4. 参数校验失败时不调用外系统；
5. Adapter 异常不被 Flow 吞掉；
6. mock API 成功路径和结果格式（原有端到端测试）；
7. Celery 自动发现申请链接 Task；
8. `apps.product_data.tasks` 可导入；
9. readiness、Catalog、Job Runner 和 HTTP 审计相关回归。

全仓 `.venv/bin/ruff format --check .` 仍失败，原因是 10 个本次未修改的历史文件与当前
Ruff 0.15.20 格式结果不一致。为避免扩大本次重构范围，没有批量改写这些无关文件；本次涉及
文件的 format 检查已经通过。

## 11. 仍存在的风险与未验证事项

- 容器没有 Python 3.10，本次自动测试运行在 Python 3.12.13；仍需在内网 Python 3.10 环境复验。
- 测试使用 SQLite 内存数据库，未连接内网 MySQL 5.7.20。
- Celery 使用 eager 模式，没有连接真实 RabbitMQ 或独立 Worker。
- mock 模式已通过；real 模式的配置缺失门禁已有测试，但真实外系统协议、Signer 和网络调用
  无法在此环境端到端验证。
- 全仓 Ruff format 历史基线未清理，详见上一节。

## 12. 内网拉取与启动验证

在内网开发仓库中执行：

```bash
git fetch origin
git switch agent/code-flow-refactor
git pull --ff-only origin agent/code-flow-refactor
git rev-parse HEAD
```

确认 Python 3.10 后，在项目根目录安装依赖；离线环境使用现有 wheelhouse：

```bash
cd Alkaid-python
make install PIP_INSTALL_ARGS="--no-index --find-links ../wheelhouse"
make check
```

Windows 开发环境已有根目录 `.venv` 时，可在仓库根目录执行：

```bat
npm run dev:env
npm run dev
```

无 RabbitMQ 的临时 mock 验证，在 `.env.local` 设置：

```text
EXTERNAL_SYSTEM_MODE=mock
CELERY_TASK_ALWAYS_EAGER=true
DEV_START_WORKER=false
```

真实异步链路验证设置：

```text
CELERY_TASK_ALWAYS_EAGER=false
DEV_START_WORKER=true
CELERY_QUEUE=alkaid-local
```

启动后依次确认：

1. `GET /health/` 返回 `status=ok`；
2. `GET /health/ready/` 返回 `status=ready`；
3. 调用原路径 `POST /api/product-data/tools/application-links/generate`；
4. Job 从 `pending/running` 进入 `success`；
5. `Job.result` 仍为 `{"links": {"internalUrl", "externalUrl", "generatedAt"}}`；
6. JobLog 有 validate/generate/completed 记录；
7. JobApiCall 恰好记录一次申请链接外部调用；
8. 独立 Worker 环境运行
   `python scripts/verify_celery_runtime.py --min-workers 1`，确认申请链接 Task 已注册。

## 13. 发布状态

重新安装并授权 ChatGPT Codex Connector 后，已成功创建并发布远程分支：

```text
agent/code-flow-refactor
```

远程分支以 `a7a4f94e208d39ca2daf30bd60f1cd0ada124cae` 为唯一基准，包含实现、测试和报告三个
逻辑提交。发布后已核对远程最终 tree SHA 与本地最终 tree SHA，二者均为：

```text
ea7eda6e3e54a3fd5525b43fe59723c8e28a3d06
```

因此远程文件内容与本地验证过的文件内容完全一致。
