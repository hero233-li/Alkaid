# Alkaid Backend

这是一个 Django + Celery 模块化单体基线，解决不同版本互相影响、网络调用重复、
跨进程全局状态和嵌套字典难以追踪的问题。

项目统一使用 Python 3.10 和 Django 4.1.13；`.python-version` 和 Ruff 目标版本保持一致。

## MySQL 版本

本地环境按现有 MySQL 5.7.20 配置。Django 固定为最后原生支持 MySQL 5.7 的 4.1.13，
数据库使用标准 `django.db.backends.mysql` 后端，不再维护自定义兼容层。

Django 4.1 和 MySQL 5.7 都已停止安全维护。这套组合用于兼容现有环境；如果服务器将来
对外提供服务，应先升级 MySQL，再升级到受支持的 Django LTS 版本。

## 本地启动

推荐使用 Python 3.10 的本机虚拟环境。运行环境默认使用本机 MySQL，并由独立 Celery Worker
消费 RabbitMQ 队列；临时没有消息队列时，开发环境可以显式设置 `CELERY_TASK_ALWAYS_EAGER=true`。
开发环境的 Mock 模式还提供了投递失败回退：RabbitMQ 不可用时会在请求进程执行已持久化的
Job，生产模式只会将 Job 标记为失败并保留可重试状态。

请先创建开发库：

```sql
CREATE DATABASE alkaid_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```bash
make install
make migrate
make run
```

离线安装时可以把 wheel 文件放到本地目录，再传给 pip：

```bash
make install PIP_INSTALL_ARGS="--no-index --find-links ../wheelhouse"
```

依赖只锁定在 `requirements-dev.lock`。修改 `pyproject.toml` 后安装 `uv` 并运行 `make lock`，
发布脚本和本机安装都会消费同一份锁文件。

服务默认地址：

- Django：`http://127.0.0.1:8000`
- 存活检查：`http://127.0.0.1:8000/health/`
- 就绪检查：`http://127.0.0.1:8000/health/ready/`

发布脚本会设置 `FRONTEND_DIST_DIR`，此时后端会直接服务 React 构建产物。生产启动器会同时
监管 Uvicorn、Celery Worker 和 Celery Beat；任一子进程异常退出时整组退出，交由 Windows
任务计划重新拉起。页面、`/api` 和 `/health/` 仍在同一个 Uvicorn 地址下。

如果已经有可用虚拟环境，也可以直接执行：

```bash
DJANGO_SETTINGS_MODULE=config.settings.local DB_ENGINE=mysql \
  MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 MYSQL_DATABASE=alkaid_dev \
  MYSQL_USER=workflow MYSQL_PASSWORD=workflow MYSQL_SSL_DISABLED=true \
  CELERY_TASK_ALWAYS_EAGER=true \
  .venv/bin/python manage.py migrate

DJANGO_SETTINGS_MODULE=config.settings.local DB_ENGINE=mysql \
  MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 MYSQL_DATABASE=alkaid_dev \
  MYSQL_USER=workflow MYSQL_PASSWORD=workflow MYSQL_SSL_DISABLED=true \
  CELERY_TASK_ALWAYS_EAGER=true \
  .venv/bin/python -m uvicorn config.asgi:application --host 127.0.0.1 --port 8000 --reload
```

## 产品申请与 Job API

`ProductApplyPage` 使用以下接口：

```text
GET  /api/product-data/applications/config
POST /api/product-data/applications
POST /api/product-data/tools/application-links/generate
GET  /api/product-data/business-access/config
POST /api/product-data/business-access/search
GET  /api/product-data/verification-approval/config
POST /api/product-data/verification-approval/search
GET  /api/jobs/{id}
POST /api/jobs/{id}/retry
POST /api/jobs/{id}/cancel
GET  /api/jobs/{id}/logs/stream?afterId=0
GET  /api/jobs/{id}/calls/{callId}
```

产品配置统一位于 `apps/product_data/configs/reference_data.json` 和
`apps/product_data/configs/products/*.json`。页面配置、后端校验、Job 快照和申请链接路由均由
这一个 Catalog 派生。

Celery 将普通过程日志写入 `JobLog`，将每次外部 HTTP 请求的脱敏请求、响应、错误和耗时写入
`JobApiCall`。日志窗口通过 ASGI SSE 增量接收日志；断线后使用最后一个 `afterId` 续传。
外部系统 Adapter 使用 `HttpClient` 时传入 `JobHttpCallObserver`，即可记录结构化调用详情。

产品申请、申请链接、业务准入和核实审批分别拥有自己的业务目录和 Integration。Mock 响应放在
各自的 `mock_transport.py`，不会写进 View、Service 或 Adapter；本地 Mock 与真实外系统共用
同一套请求模型、HTTP Client 和响应校验。完整边界见 `apps/integrations/README.md` 和
`apps/product_data/README.md`。

产品申请 payload 必须提交明确的客户类型枚举 `customerType`：`farmer`、`legal_person` 或
`shareholder`。`legal_person` 和 `shareholder` 必须同时提交非空 `companyName`；`farmer`
不能提交企业名称。旧的 `legalPerson` 布尔字段仅用于前端 Switch 状态，不再作为后端业务字段。

示例配置提供产品 A、B、C：产品 A 使用 `whitelistEnabled`（白名单），产品 B 使用
`redShieldEnabled`（红盾），产品 C 使用 `creditEnabled`（征信）。每个 Switch 直接定义在所属
产品文件中；后端只接受当前产品配置的字段，提交其他产品的 Switch 会返回参数错误。

Mock 产品执行流程同时演示两类认证：`product_flow` 在当前 Celery attempt 内先从登录响应体
获取 Token，普通检查接口只使用不更新，刷新接口从响应 Header 更新 Token，后续申请接口使用
新 Token；`fixed_external` 从 `MOCK_FIXED_SYSTEM_TOKEN` 环境变量读取固定 Token。认证策略由
`EndpointSpec` 声明，Token 按单次请求注入且不会写入 Job payload、结果或明文审计日志。
HTTP 连接、读写和连接池超时分别可配置；只有显式声明为 `RetryMode.SAFE` 的登录/查询类端点
才会按 `Retry-After` 或指数退避重试，创建申请等写接口默认不自动重放。

后端产品执行配置与前端展示配置不再分开维护。每个产品文件自包含页面字段、申请方式、必填规则
和产品功能路由；运行时通过 Pydantic 加载并派生所需视图。产品调用顺序直接由业务服务表达，
不再通过只修改常量的 Handler 子类和注册表间接选择。

修改产品配置后运行：

```bash
.venv/bin/python scripts/compile_product_config.py --check
```

该命令只做校验，不再生成另一份运行时 Catalog；同时检查产品到外系统端点的覆盖关系和全部
原始报文结构。Catalog 在 Web/Worker 进程内缓存，修改 JSON 后需重启整组服务。创建 Job 时仍
保存解析后的方法快照，已排队任务及重试不会因产品文件更新而改变执行方式。

## 代码边界

- `apps/integrations/http.py`：唯一通用 HTTP 传输层。
- `apps/integrations/<system>/`：外部系统报文和 Adapter；原始 JSON 不能越过此边界。
- `apps/jobs/`：异步任务状态、日志、外部调用审计、重试、取消和 SSE。
- `apps/product_data/catalog.py`：产品配置的唯一加载、校验和 Job 快照入口。

页面业务按域拆分到 `apps/product_data/<feature>/`。`product_applications/` 负责产品申请，
`application_links/` 负责申请链接生成；两者只保留自己的 Schema、HTTP 入口、任务和业务服务，
并共享 `jobs` 基础设施。当前产品共用的调用顺序直接写在
`product_applications/services.py`；只有出现真实差异时才增加独立业务函数。外部系统实现位于
`apps/integrations/<system>/`，业务层不拼接原始报文，也不直接调用 HTTP。

业务模块禁止直接导入 `requests` 或 `httpx`。运行 `python scripts/check_architecture.py`
检查这一约束。

## 多版本并行

本机开发、发布候选验证和生产运行必须使用不同 MySQL 数据库：

```text
alkaid_dev
alkaid_verify
alkaid_prod
```

开发目录只连接 `alkaid_dev`。发布候选只连接 `alkaid_verify`。生产启动只连接 `alkaid_prod`。
不要让未验证代码直接连接生产库。

完整发布流程见项目根目录的 `docs/LOCAL_RELEASE_WORKFLOW.md`。

## 验证

```bash
make check
python scripts/check_architecture.py
```

Job 默认保留30天，JobLog 和接口调用详情默认保留7天。Celery Beat 每分钟收敛超过 deadline
仍未结束的任务，并每小时清理过期记录；Worker 丢失后，同一 Celery 投递可以继续恢复该 Job。

从已部署过旧示例 Workflow 的数据库升级时，移除 Django App 不会自动删除原有 Workflow
数据表。确认历史数据无需保留后，再由 DBA 在备份基础上安排表清理；应用发布本身不执行自动
DROP，避免误删数据。
