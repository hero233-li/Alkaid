# Workflow Backend

这是一个 Django + Celery 模块化单体基线，解决不同版本互相影响、网络调用重复、
跨进程全局状态和嵌套字典难以追踪的问题。

项目统一使用 Python 3.10 和 Django 4.1.13；`.python-version` 和 Ruff 目标版本保持一致。

## MySQL 版本

本地环境按现有 MySQL 5.7.20 配置。Django 固定为最后原生支持 MySQL 5.7 的 4.1.13，
数据库使用标准 `django.db.backends.mysql` 后端，不再维护自定义兼容层。

Django 4.1 和 MySQL 5.7 都已停止安全维护。这套组合用于兼容现有环境；如果服务器将来
对外提供服务，应先升级 MySQL，再升级到受支持的 Django LTS 版本。

## 本地启动

推荐使用 Python 3.10 的本机虚拟环境。运行环境默认使用本机 MySQL，并开启 Celery eager 模式，
不需要消息队列。

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

服务默认地址：

- Django：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/health/`

发布脚本会设置 `FRONTEND_DIST_DIR`，此时后端会直接服务 React 构建产物。生产入口只需要一个
Uvicorn 端口，页面、`/api` 和 `/health/` 都在同一个地址下。

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

## Workflow API

启动流程：

```http
POST /api/workflows/
Content-Type: application/json

{
  "idempotency_key": "frontend-request-001",
  "input": {"value": " example value "}
}
```

首次请求返回 `202`；相同 `idempotency_key` 和输入返回原 Workflow 与 `200`，不会重复投递任务。
同一幂等键提交不同输入会返回 `409`。失败后整次重跑时必须生成新的幂等键。

```json
{
  "workflow_id": "2cbb2ca1-736a-43f8-b160-265c8db66a83",
  "status": "pending",
  "created": true
}
```

查询状态：

```http
GET /api/workflows/{workflow_id}/
```

## 产品申请与 Job API

`ProductApplyPage` 使用以下接口：

```text
GET  /api/product-data/applications/config
POST /api/product-data/applications
GET  /api/jobs/{id}
POST /api/jobs/{id}/retry
POST /api/jobs/{id}/cancel
GET  /api/jobs/{id}/logs/stream?afterId=0
GET  /api/jobs/{id}/calls/{callId}
```

产品配置位于 `apps/product_data/configs/product_application.json`。仓库中的配置和处理器仅为
可运行示例；接入真实产品前必须替换环境、产品、机构数据，并在
`ProductApplicationExecutor` 中注册真实 Adapter。

Celery 将普通过程日志写入 `JobLog`，将每次外部 HTTP 请求的脱敏请求、响应、错误和耗时写入
`JobApiCall`。日志窗口通过 ASGI SSE 增量接收日志；断线后使用最后一个 `afterId` 续传。
外部系统 Adapter 使用 `HttpClient` 时传入 `JobHttpCallObserver`，即可记录结构化调用详情。

产品申请 payload 必须提交明确的客户类型枚举 `customerType`：`farmer`、`legal_person` 或
`shareholder`。`legal_person` 和 `shareholder` 必须同时提交非空 `companyName`；`farmer`
不能提交企业名称。旧的 `legalPerson` 布尔字段仅用于前端 Switch 状态，不再作为后端业务字段。

示例配置提供产品 A、B、C：产品 A 使用 `whitelistEnabled`（白名单），产品 B 使用
`redShieldEnabled`（红盾），产品 C 使用 `creditEnabled`（征信）。Switch 字段通过
`products` 数组声明适用产品；后端只接受当前产品关联的 Switch，提交其他产品的 Switch
会返回参数错误。

Mock 产品执行流程同时演示两类认证：`product_flow` 在当前 Celery attempt 内先从登录响应体
获取 Token，普通检查接口只使用不更新，刷新接口从响应 Header 更新 Token，后续申请接口使用
新 Token；`fixed_external` 从 `MOCK_FIXED_SYSTEM_TOKEN` 环境变量读取固定 Token。认证策略由
`EndpointSpec` 声明，Token 按单次请求注入且不会写入 Job payload、结果或明文审计日志。

后端产品执行配置与前端展示配置分离。前端仍读取
`apps/product_data/configs/product_application.json`；后端配置源码位于
`apps/product_data/configs/execution/source/`，分别维护字段目录、字段组和各产品的申请方式、
归属类别、机构、动态字段及公共字段。运行时只读取校验后的
`apps/product_data/configs/execution/compiled/product_catalog.json`，业务代码通过 Pydantic 对象
访问配置，不操作多层 dict。

修改执行配置后运行：

```bash
.venv/bin/python scripts/compile_product_config.py
.venv/bin/python scripts/compile_product_config.py --check
```

创建 Job 时会保存执行配置版本和解析后的方法快照。已排队任务及重试继续使用原快照，不会因
配置目录更新而改变执行方式。请求未指定 `applicationMethod` 时使用产品默认方式；选择动态
方式时，只校验该方式解析出的动态字段。

## 代码边界

- `apps/integrations/http.py`：唯一通用 HTTP 传输层。
- `apps/integrations/<system>/`：外部系统报文和 Adapter；原始 JSON 不能越过此边界。
- `apps/workflows/schemas.py`：Pydantic 请求、响应和 Context。
- `apps/workflows/services.py`：Workflow 编排和状态的唯一写入口。
- `apps/workflows/tasks.py`：本地、测试和服务器共用的 Celery Task。

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

Workflow 成功或失败后默认保留24小时。Job 默认保留30天，JobLog 和接口调用详情默认保留
7天，Celery Beat 每小时清理过期记录。
