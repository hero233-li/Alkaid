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

数据中心的文档、在线表格、多维表格及文件夹通过 `apps.workflow.Documents` 持久化到 MySQL。
部署新版本后必须执行 `make migrate`，以创建文档、文件夹和图片资源表。列表接口只返回
元数据，正文由文件详情接口按需读取；创建、修改、移动和删除均使用单文件接口，不再重建
整个 workspace。编辑器图片通过 `/api/documents/assets` 单独上传，正文仅保留图片 URL，避免
Base64 令正文和浏览器缓存膨胀。

正文及请求默认上限是 128 MiB，单张图片默认上限是 32 MiB，可通过以下变量调整：

```text
DATA_DOCUMENT_MAX_CONTENT_BYTES=134217728
DATA_DOCUMENT_MAX_ASSET_BYTES=33554432
DJANGO_MAX_REQUEST_BYTES=268435456
DJANGO_FILE_MEMORY_THRESHOLD_BYTES=2621440
```

Nginx 和 MySQL 还需要采用 `deploy/nginx/alkaid-upload.conf.example` 与
`deploy/mysql/alkaid-large-documents.cnf.example` 中的匹配上限。图片拆分后，即使一个文档的
全部资源超过 100 MiB，列表和正文也不会重复传输所有图片；但浏览器一次渲染大量原始大图
仍会消耗内存，生产环境建议在上传阶段进一步生成缩略图和 WebP/AVIF。

旧版 `.doc` 导入和在线 Word 的 `.docx` 导出按以下顺序选择转换能力：LibreOffice、Windows
上已安装的 Microsoft Word（PowerShell COM）、macOS 系统自带 `textutil`。因此 Windows
已经安装 Word 或 macOS 使用系统组件时，无需安装 LibreOffice。自定义 LibreOffice 路径可设置：

```text
LIBREOFFICE_BINARY=C:\Program Files\LibreOffice\program\soffice.exe
```

纯 Linux 服务器仍建议安装 `libreoffice-writer`。Windows 如果既没有 Microsoft Word 也没有
LibreOffice，二进制 `.doc` 无法仅靠纯 Python 可靠保留图片、表格和复杂排版。

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
GET  /api/jobs/{id}/payload
POST /api/jobs/{id}/retry
POST /api/jobs/{id}/cancel
GET  /api/jobs/{id}/logs/stream?afterId=0
GET  /api/jobs/{id}/calls/{callId}
```

产品配置统一位于 `apps/config/products/reference_data.json` 和
`apps/config/products/*.json`。页面配置、后端校验、Job 快照和申请链接路由均由
这一个 Catalog 派生。

Celery 将普通过程日志写入 `JobLog`，将每次外部 HTTP 请求的原文 URL、Header、请求、响应、
异常和耗时写入 `JobApiCall`。不再进行字段脱敏或省略 Base64；只使用
`JOB_MAX_HTTP_BODY_BYTES` 统一保存原文前缀和总字节数。日志窗口通过 ASGI SSE 增量接收日志；
断线后使用最后一个 `afterId` 续传。
外部系统只依赖中立 `IntegrationObserver`；Celery Task 组装
`JobIntegrationObserver`，把结构化请求、响应与诊断写入 `JobApiCall`/`JobLog`。Integration 不再
持有 `Job` ORM，也不直接调用 Job 日志服务。

产品申请、申请链接、业务准入和核实审批分别拥有自己的同级功能 App。业务 Mock 响应放在
各功能的 `mock.py`，公共 `MockTransportRouter` 位于 `apps/mock/mock.py`；本地 Mock 与真实外系统共用
同一套请求模型、HTTP Client 和响应校验。通用 HTTP、Java 网关和产品目录分别位于
`apps/utils/http`、`apps/utils/java` 和 `apps/utils/product_Conf`。

产品申请 payload 必须提交明确的客户类型枚举 `customerType`：`farmer`、`legal_person` 或
`shareholder`。`legal_person` 和 `shareholder` 必须同时提交非空 `companyName`；`farmer`
不能提交企业名称。旧的 `legalPerson` 布尔字段仅用于前端 Switch 状态，不再作为后端业务字段。

示例配置提供产品 A、B、C：产品 A 使用 `whitelistEnabled`（白名单），产品 B 使用
`redShieldEnabled`（红盾），产品 C 使用 `creditEnabled`（征信）。每个 Switch 直接定义在所属
产品文件中；后端只接受当前产品配置的字段，提交其他产品的 Switch 会返回参数错误。

HTTP 连接、读写和连接池超时分别可配置。`RetryMode.NEVER` 不重试，
`CONNECT_ONLY` 仅在能确认尚未发出请求的连接失败时重试，`IDEMPOTENT` 才允许对连接/读取失败和
指定 5xx 重试；退避带 jitter。CJDK 的 Session、协议查询、预览和文档 POST 当前全部为
`NEVER`，未自行添加幂等键。

CJDK Session 目前只实现“打开申请页面、逐跳验证 URL、收集 Cookie/响应头、按环境
`SessionRequirement` 判定状态”。真实 auth/TokenId 初始化接口尚未提供，因此没有猜测接口路径或
字段；要求不满足时状态为 `page_opened`/`partial`，流程会在协议查询前停止。每个环境必须配置
允许的 scheme/host/port、跨 Host 跳转规则和 Session Header 转发白名单。

接口工作台生产默认关闭（`WORKBENCH_ENABLED=false`），关闭时后端路由不注册。若显式启用，还需
配置 `WORKBENCH_ALLOWED_HOSTS`；目标 IP、重定向和协议级请求头会被检查。Cookie、Authorization
等认证头会转发并保存在历史记录中；当前项目没有用户认证与租户隔离能力，因此不应在生产启用。

后端产品执行配置与前端展示配置不再分开维护。每个产品文件自包含页面字段、申请方式、必填规则
和产品功能路由；运行时通过 Pydantic 加载并派生所需视图。产品调用顺序直接由业务服务表达，
不再通过只修改常量的 Handler 子类和注册表间接选择。

修改产品配置后运行：

```bash
.venv/bin/python scripts/compile_product_config.py --check
```

该命令只做校验，不再生成另一份运行时 Catalog；同时检查当前 CJDK-JYRC 原始报文结构。
Catalog 在 Web/Worker 进程内缓存，修改 JSON 后需重启整组服务。创建 Job 时仍
保存解析后的方法快照，已排队任务及重试不会因产品文件更新而改变执行方式。

## 代码边界

- `apps/utils/http/`：统一 HTTP 协议、观察协议和客户端实现。
- `apps/utils/java/`：统一 Java Gateway 实现。
- `apps/mock/`：公共 HTTP Mock 基础设施。
- `apps/workflow/product_applications/cjdk/`：CJDK 申请、协议、身份和业务 Mock 的功能私有实现。
- `apps/workflow/Jobs/`：异步任务状态、日志、外部调用审计、重试、取消和 SSE。
- `apps/utils/product_Conf/catalog.py`：产品配置的唯一加载、校验和 Job 快照入口。

页面业务统一放在 `apps/workflow/` 下按功能 App 拆分。`product_applications` 负责当前完整申请后端；后续业务使用
`apps/workflow/business_access`、`apps/workflow/loan_status` 等新 App，并共享 `Jobs` 与公共集成基础设施。
`workflow.py` 只编排业务流程，外部能力由运行时实现提供，`tasks.py` 是唯一运行时组合入口。

项目统一使用已安装的 `httpx`，不使用 `requests`。运行 `python scripts/check_architecture.py`
递归检查公共层、产品目录和功能实现的依赖边界。

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
python manage.py makemigrations --check --dry-run
python scripts/verify_celery_runtime.py --min-workers 2
```

前端测试与构建从仓库根目录旁的 `Alkaid-react` 执行：

```bash
npm test -- --run
npm run build
```

接口、调用链、环境变量、数据库迁移和完整测试矩阵见
[`../docs/ASYNC_WORKFLOW_OPERATIONS.md`](../docs/ASYNC_WORKFLOW_OPERATIONS.md)。

Job 默认保留30天，JobLog 和接口调用详情默认保留7天。Celery Beat 每分钟收敛超过 deadline
仍未结束的任务，并每小时清理过期记录；Worker 丢失后，同一 Celery 投递可以继续恢复该 Job。

从已部署过旧示例 Workflow 的数据库升级时，移除 Django App 不会自动删除原有 Workflow
数据表。确认历史数据无需保留后，再由 DBA 在备份基础上安排表清理；应用发布本身不执行自动
DROP，避免误删数据。
