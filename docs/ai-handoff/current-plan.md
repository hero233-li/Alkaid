# 四个产品数据功能当前调用链调查与建议方案

> 调查日期：2026-07-13  
> 调查范围：产品申请、申请链接获取、业务准入、核实审批  
> 调查原则：以当前工作区真实代码为准，不假设四条链采用相同执行模型。  
> 注意：当前工作区已有未提交改动，包括申请链接 Adapter 的调试日志，以及 macOS/Windows
> 开发启动日志改为只输出终端。本次调查没有修改业务代码，只新增本文档。

## 0. 范围与术语

项目没有使用 Django REST Framework，也不存在 DRF `Serializer`。本文中的“Serializer 层”实际
对应两类 Pydantic 模型：

1. `apps/product_data/<domain>/schemas.py`：前端 HTTP 请求、Job payload、执行快照和业务结果契约。
2. `apps/integrations/<system>/models.py`：外系统请求和响应的 wire contract。

前三个功能使用统一 `Job` + Celery 异步模型；核实审批当前是同步 HTTP 调用，没有 Task，也没有
写入 `Job`、`JobLog` 或 `JobApiCall`。

## 1. 当前真实调用链

### 1.1 公共入口与公共基础设施

所有后端业务路由都挂载在：

```text
config/urls.py
  /api/product-data/ -> apps/product_data/urls.py
  /api/jobs/         -> apps/jobs/urls.py
```

异步功能公共链路：

```text
前端 POST + X-Idempotency-Key + X-Trace-ID
  -> Domain View 校验并 create_job()
  -> transaction.on_commit(enqueue_job)
  -> Celery task.delay(job.id)
  -> Domain Task
  -> Domain Service
  -> Integration Adapter
  -> EndpointExecutor
  -> HttpClient
  -> MockTransport 或真实外系统
  -> JobApiCall / JobLog 审计
  -> Task mark_job_success()/mark_job_failed()
  -> 前端 GET /api/jobs/{id} 轮询，产品申请详情另支持 SSE 日志
```

RabbitMQ 不可用时：

- `DEBUG=True` 且 `EXTERNAL_SYSTEM_MODE=mock`：`enqueue_job()` 在 Web 进程同步 `task.apply()`。
- 生产或真实外系统模式：Job 被标记为失败，不回退同步执行。
- `CELERY_TASK_ALWAYS_EAGER=true`：`delay()` 本身已同步执行，不做第二次 fallback。

### 1.2 产品申请

#### 前端

```text
menuConfig.tsx
  -> ProductApplyPage/index.tsx
  -> useProductConfig(): GET /api/product-data/applications/config
  -> useProductApplicationForm(): 根据后端 Catalog 派生动态表单
  -> model/submission.ts: buildProductSubmission()
  -> productApplicationApi.ts: POST /api/product-data/applications
  -> useProductApplyJobs(): GET /api/jobs/{id}、SSE 日志、retry、cancel
```

提交结构：

```json
{
  "name": "产品显示名-产品申请",
  "product": "稳定产品代码",
  "payload": {
    "environment": "环境代码",
    "product": "稳定产品代码",
    "location": "...",
    "branch": "...",
    "outlet": "...",
    "customerType": "farmer | legal_person | shareholder",
    "applicationMethod": "...",
    "...产品字段": "..."
  }
}
```

#### 后端

```text
POST /api/product-data/applications
  -> product_applications/views.py:create_product_application
  -> ProductApplicationSubmission.model_validate_json()
  -> load_product_catalog().snapshot(product, applicationMethod)
  -> validate_submission(..., catalog=...)
  -> create_job(kind="product_application", payload=payload,
                execution_config_snapshot=ProductExecutionSnapshot)
  -> jobs/dispatch.py -> execute_product_application.delay(job.id)
  -> product_applications/tasks.py:execute_product_application
  -> resolve_product_snapshot() + validate_submission()
  -> run_product_application()
  -> _run_mock_product_flow()
  -> MockProductApplicationAdapter
```

外系统调用顺序固定为五次：

```text
1. POST /auth/token                       获取流程 Token
2. POST /checks/{product-specific-path}  产品检查
3. POST /auth/rotate                     更新流程 Token
4. POST /applications                    提交申请
5. POST /fixed/audit                     固定 Token 审计调用
```

Token 行为：

- `product_flow` 使用 `FlowTokenProvider`，只存在当前 Job attempt 的内存中。
- 登录响应体 `data.token` 写入版本 1。
- `/auth/rotate` 响应 Header `X-New-Token` 更新为版本 2。
- 检查和提交使用 `Authorization: Bearer <flow token>`。
- `fixed_external` 从 `MOCK_FIXED_SYSTEM_TOKEN` 环境变量读取，使用 `X-Api-Token`，禁止响应更新。

### 1.3 申请链接获取

#### 前端

```text
menuConfig.tsx
  -> ApplicationLinkGeneratorPage/index.tsx
  -> useApplicationLinkForm()
  -> 前端静态 applicationLinkConfig.ts
  -> model/submission.ts: buildApplicationLinkSubmission()
  -> api/applicationLink.ts:
       POST /api/product-data/tools/application-links/generate
  -> 每 400ms GET /api/jobs/{id}
  -> extractApplicationLinkResult()
```

动态链接时，前端把 TextArea 中的 JSON 字符串解析为 `requestJson` 对象后再提交。

#### 后端

```text
POST /api/product-data/tools/application-links/generate
  -> application_links/views.py:generate_application_link
  -> ApplicationLinkSubmission.model_validate_json()
  -> resolve_execution_snapshot(): 从统一 ProductCatalog 冻结产品/环境/类别/必填字段
  -> create_job(kind="application_link_generation", snapshot=...)
  -> jobs/dispatch.py -> execute_application_link.delay(job.id)
  -> application_links/tasks.py:execute_application_link
  -> validate_submission()
  -> generate_application_links()
  -> ApplicationLinkAdapter.create_application()
  -> ApplicationLinkAdapter.generate_links()
```

外系统调用：

```text
1. POST /applications
   body = { product, category, payload: 完整 ApplicationLinkSubmission }

2a. 太阳码：POST /links/sun-code
2b. 动态链接：POST /links/dynamic
   body = { application_no, product, category }
```

真实模式 Token：

```text
APPLICATION_LINK_API_TOKEN
  -> Django settings
  -> HttpClientConfig.token
  -> Authorization: Bearer <token>
```

这是静态 Token。当前没有登录、刷新、过期检测或响应更新；修改环境变量后需重启 Web/Worker。

### 1.4 业务准入

#### 前端

```text
menuConfig.tsx
  -> BusinessAccessPage/index.tsx
  -> useBusinessAccessForm(): GET /api/product-data/business-access/config
  -> useBusinessAccess(): runWorkflow()
  -> api/businessAccess.ts 创建 Job
  -> 每 500ms GET /api/jobs/{id}
  -> model/jobModel.ts 提取不同 operation 的 result
```

四种操作入口：

```text
POST /api/product-data/business-access/search
POST /api/product-data/business-access/{recordId}/invalidate
POST /api/product-data/business-access/{recordId}/notifications/query
POST /api/product-data/business-access/{recordId}/notifications/{notificationId}/push-new|push-old
```

#### 后端

```text
business_access/views.py
  -> Pydantic Submission 或路径参数构造 Submission
  -> _submit_job()
  -> create_job(kind="business_access.<operation>",
                snapshot={operation, version: 1})
  -> jobs/dispatch.py -> execute_business_access_task.delay(job.id)
  -> business_access/tasks.py
  -> execute_business_access(job, operation)
  -> BusinessAccessAdapter
```

每个 Job 对应一次外系统调用：

```text
search         -> POST /access/records/search
invalidate     -> POST /access/records/{id}/invalidate
notifications  -> POST /access/records/{id}/notifications/query
push           -> POST /access/records/{id}/notifications/{notificationId}/push
```

真实模式使用静态 `BUSINESS_ACCESS_API_TOKEN`，由 `HttpClient` 注入 Bearer Header，不自动更新。

### 1.5 核实审批

#### 前端

```text
menuConfig.tsx
  -> VerificationApprovalPage/index.tsx
  -> useVerificationApprovalForm(): GET /api/product-data/verification-approval/config
  -> useVerificationApproval()
  -> api/verificationApproval.ts 直接等待同步响应
```

请求入口：

```text
POST /api/product-data/verification-approval/search
POST /api/product-data/verification-approval/{taskId}/claim
POST /api/product-data/verification-approval/{taskId}/return
POST /api/product-data/verification-approval/{taskId}/items/{itemId}
POST /api/product-data/verification-approval/{taskId}/actions/{action}
```

除 search 外，前端都会把当前完整 `VerificationTask` 作为 `context` 回传。

#### 后端

```text
verification_approval/views.py
  -> Pydantic Submission
  -> 生成/规范 X-Trace-ID
  -> verification_approval/services.py
  -> VerificationApprovalAdapter(trace_id)
  -> EndpointExecutor -> HttpClient
  -> 同步返回前端
```

该链没有以下环节：

```text
没有 Celery Task
没有 Job
没有 JobLog
没有 JobApiCall
没有 retry/cancel/status polling
```

外系统路径与前端操作一一对应。真实模式使用静态 `VERIFICATION_APPROVAL_API_TOKEN`，不自动更新。

### 1.6 四功能层级定位矩阵

| 功能 | 前端请求入口 | View | Pydantic Serializer/Schema | Task | Service | 数据库模型 | 外系统调用位置 | 主要现有测试 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 产品申请 | `ProductApplyPage/api/productApplicationApi.ts` | `product_applications/views.py` | `product_applications/schemas.py`；`integrations/mock_product/models/` | `product_applications/tasks.py` | `product_applications/services.py` | `Job`、`JobLog`、`JobApiCall`；无专属业务表 | `integrations/mock_product/adapters/application.py`、`client.py` | `test_api.py`、`test_catalog_and_messages.py`、`test_runtime_mode.py` |
| 申请链接 | `ApplicationLinkGeneratorPage/api/applicationLink.ts` | `application_links/views.py` | `application_links/schemas.py`；`integrations/application_link/models.py` | `application_links/tasks.py` | `application_links/services.py` | `Job`、`JobLog`、`JobApiCall`；无专属业务表 | `integrations/application_link/adapter.py` | `test_api.py` |
| 业务准入 | `BusinessAccessPage/api/businessAccess.ts` | `business_access/views.py` | `business_access/schemas.py`；`integrations/business_access/models.py` | `business_access/tasks.py` | `business_access/services.py` | `Job`、`JobLog`、`JobApiCall`；Mock 业务状态仅内存 Store | `integrations/business_access/adapter.py` | `test_business_features.py` |
| 核实审批 | `VerificationApprovalPage/api/verificationApproval.ts` | `verification_approval/views.py` | `verification_approval/schemas.py`；`integrations/verification_approval/models.py` | **不存在** | `verification_approval/services.py` | **没有 Job/审计表**；Mock 任务状态仅内存 Store | `integrations/verification_approval/adapter.py` | `test_business_features.py` |

## 2. 各层当前职责

| 层 | 当前职责 | 备注 |
| --- | --- | --- |
| 前端页面/Hook | 表单状态、级联选项、提交、轮询或同步交互、结果展示 | 产品申请使用后端动态配置；申请链接仍使用前端静态配置 |
| 前端 API | 组装 URL、Trace/幂等 Header、解析统一 `{ok,data,message}` | 申请链接使用独立 Axios client；其余多使用共享 `apiClient` |
| View | HTTP 方法限制、Pydantic 校验、错误映射、Job 创建或同步调用 | 所有写接口均 `csrf_exempt` |
| Pydantic Schema | 前端输入、Job payload、快照、业务结果约束 | 替代传统 Serializer |
| Task | 异步状态机、超时、取消检查、进度和最终状态 | 仅产品申请、申请链接、业务准入存在 |
| Service | 业务校验、配置解析、调用顺序、语义请求构造、结果整形 | 不直接导入 `httpx` |
| Domain DB | 没有四个功能专属业务表 | 异步链统一使用 Job 系列表 |
| Job DB | `Job` 保存 payload/result/snapshot/status；`JobLog` 保存业务日志；`JobApiCall` 保存脱敏外调审计 | 核实审批不使用 |
| Integration Adapter | 把业务语义模型映射为外系统 Endpoint 调用 | 产品申请 Adapter 还负责长报文填充 |
| EndpointSpec | 声明方法、路径、响应模型、业务成功码、认证、Token 更新、重试安全性 | 写操作默认 `RetryMode.NEVER` |
| TokenManager | 按 EndpointSpec 注入或更新流程 Token | 目前只有产品申请真正注册 Provider |
| HttpClient | 超时、Trace Header、序列化、重试、HTTP/响应校验、基础日志 | 静态 Token 在 Client 初始化时放入默认 Header |
| MockTransport | 模拟真实外系统协议与状态 | 业务准入、核实审批 Mock Store 只在进程内存中存在 |
| ProductCatalog | 产品申请 UI 配置、字段规则、产品快照、申请链接路由的单一后端来源 | 默认缓存，配置变化需要重启各进程 |

## 3. 当前存在的问题

### 3.1 高优先级

1. **核实审批与其他三条链缺少一致的可靠性和审计能力。** 其外系统写操作同步执行，没有 Job
   幂等、持久化状态、超时状态机、取消、重试或 `JobApiCall` 脱敏审计。网络断开后，前端无法判断
   外系统是否已成功执行。
2. **外部 API 与 Job 查询接口没有业务认证/授权边界。** 当前写接口普遍 `csrf_exempt`，Job 详情还
   返回原始 `payload`。如果内网网关没有完成身份认证、访问控制和 TLS，这会暴露证件号、卡号、
   手机号以及可执行操作接口。
3. **三个静态外系统 Token 不支持轮换或自动刷新。** 申请链接、业务准入、核实审批只在进程启动时
   从环境变量读取 Bearer Token；Token 失效后只能修改配置并重启 Web/Worker。
4. **异步任务可能重复触发外系统写操作。** Task 使用 `acks_late` 和 worker-lost redelivery；创建申请、
   失效、推送等外系统写请求没有向外系统传递明确幂等键。当前只保证本系统 `Job` 创建幂等，不能
   保证 worker 在“外系统成功、本地尚未落库”时不重复写外系统。

### 3.2 中优先级

1. **申请链接配置存在双源。** 前端 `applicationLinkConfig.ts` 硬编码环境、产品名称、类别和额外字段，
   后端又从 ProductCatalog 校验路由。两边容易漂移。
2. **申请链接产品标识不统一。** 前端发送“产品A/产品B/产品C”显示名称，后端测试发送
   `product-a/product-b/product-c` 稳定代码；后端 Catalog 同时兼容名称和代码，导致 Job snapshot、
   外系统 body 和生成编号可能使用不同标识。
3. **当前申请链接 Adapter 反向依赖业务层。** 工作区现有调试日志让
   `apps/integrations/application_link/adapter.py` 导入 `apps.product_data.catalog`。这违反理想依赖方向，
   且 `DEBUG=True` 时一次原本可执行的外调可能因 Catalog/日志准备失败而失败。
4. **申请链接调试日志未经统一脱敏。** `request_body` 可能包含手机号、证件号和企业信息；它绕过
   `JobHttpCallObserver.sanitize()` 直接进入终端结构化日志。虽然当前仅 `DEBUG=True` 输出，仍可能在
   共享开发环境泄露数据。
5. **核实审批依赖客户端回传完整任务上下文。** 没有版本号/ETag/乐观锁；多个浏览器或过期页面可能
   回传陈旧状态。真实外系统是否把 context 当作命令必要输入尚未确认。
6. **前端异步体验不一致。** 产品申请支持缓存、轮询、SSE、retry、cancel；申请链接和业务准入只做
   无限轮询，没有 AbortSignal、客户端截止时间、重试/取消入口或页面恢复能力。
7. **业务准入前端类型与真实响应不完全一致。** `BusinessAccessJobSubmission` 声明了 `operation`，但
   后端 `serialize_job()` 不返回该字段；当前 Hook 依靠调用时传入的 operation，所以运行未报错，但
   类型契约不真实。
8. **配置来源不统一。** 产品申请使用 ProductCatalog；申请链接前端静态配置；业务准入环境和核实审批
   环境/类别分别硬编码在 Service 常量中。
9. **真实模式命名仍带 Mock 语义。** 产品申请真实外系统配置仍叫 `MOCK_PRODUCT_BASE_URL`、客户端仍叫
   `MockProductClient`，会增加内网配置和运维理解成本。

### 3.3 测试与可维护性问题

1. 没有发现四个前端功能的单元/组件测试。
2. 后端主要覆盖 Mock 成功链；缺少四个 Adapter 在真实配置下的 Header、URL、错误映射测试。
3. `FlowTokenProvider`、`StaticTokenProvider`、响应体/Header Token 更新没有直接单元测试。
4. 缺少静态 Token 401、动态 Token 缺失、刷新失败、Token 轮换和并发 Job 隔离测试。
5. 核实审批没有外调审计测试，因为当前没有 Observer/Job；也缺少并发/陈旧 context 测试。
6. 申请链接现有 API 测试直接断言调试日志内容，使业务端到端测试与临时诊断实现耦合。
7. 业务准入只断言 search 的 `api_calls.count()==1`，未逐项验证失效、通知查询和推送的审计内容与
   敏感字段脱敏。
8. `check_architecture.py` 只禁止业务层直接导入 `requests/httpx`，不能发现 Integration 反向导入
   `product_data` 等依赖方向问题。

### 3.4 当前已有的正确约束

以下能力应保留，不建议在后续改造中破坏：

- ProductCatalog 为产品申请和后端申请链接路由提供统一校验与快照。
- Job 在数据库事务提交后才投递 Celery。
- Job 创建有幂等键冲突检测，Header 长度在写数据库前校验。
- 产品申请和申请链接冻结执行快照，历史 Job 不直接依赖最新配置。
- `EndpointSpec` 区分安全重试与禁止自动重放的写操作。
- `JobHttpCallObserver` 对 Authorization、Token、手机号、证件号、卡号等递归脱敏并限制 Body 大小。
- 真实模式缺少 Base URL/Token 时启动失败，不会静默回退 Mock。

## 4. 建议修改方案

建议分阶段实施，先确认外系统合同，再统一基础能力，避免一次性重写四条链。

### 阶段 A：确认外系统与安全合同

1. 为四个外系统整理正式接口清单：Base URL、路径、请求/响应样例、成功码、超时、是否支持幂等键。
2. 分别确认认证方式：静态 Token、登录 Token、刷新 Token、过期时间、401 后处理、Header 名称。
3. 确认内网是否已有网关认证、用户身份传递、TLS 和接口授权；若没有，后端必须补齐。
4. 明确核实审批是否必须同步。如果写操作要求审计、重试、断线恢复，建议迁入 Job；如果必须同步，
   至少需要独立持久化外调审计和请求幂等机制。

### 阶段 B：统一 Token 与外系统调用策略

1. 固定密钥继续由环境变量/内网 Secret 管理注入，不将明文 access token 写入 Job 或普通数据库表。
2. 为每个系统明确注册 TokenProvider；不要同时混用 `HttpClientConfig.token` 和空 `TokenManager({})`
   表达认证。
3. 如果外系统支持登录/刷新，复用 `AuthSpec + TokenUpdateSpec`，补充 expires_at、提前刷新、401 单次
   刷新重放以及并发刷新锁。
4. 决定动态 Token 的共享范围：单 Job、单 Worker、全服务。若跨 Worker 共享，使用内网 Secret
   服务或带加密/TTL/锁的共享存储，不能只靠进程内存。
5. 对外系统写操作传递稳定幂等键，建议由 `job.workflow_id + step + attempt policy` 派生；具体 Header
   必须以真实外系统协议为准。

### 阶段 C：统一配置与标识

1. 增加申请链接配置 API，由后端 ProductCatalog 派生前端所需环境、产品、类别和额外字段。
2. 前后端与外系统请求统一使用稳定产品代码；显示名称只用于 UI。
3. 评估业务准入、核实审批选项是否来自真实外系统/配置文件；避免继续散落 Service 常量。
4. 将申请链接调试数据准备移出 Integration Adapter。需要诊断时由 Service 传入已解析的只读上下文，
   或使用统一的脱敏诊断函数；全量日志保持显式开关且默认关闭。

### 阶段 D：统一执行与审计

1. 推荐把核实审批 mutation（claim、return、item update、quick action）改为异步 Job；search 是否异步
   可根据响应时延决定。
2. 如果核实审批保留同步，新增与 `JobHttpCallObserver` 同等脱敏能力的同步审计 Observer，并增加
   请求幂等记录；不要复用一个不存在的伪 Job。
3. 统一四条链的前端 Job Hook：轮询取消、客户端截止时间、页面恢复、retry/cancel 和错误展示。
4. 收紧 `serialize_job()`：默认不要向普通列表/轮询响应返回完整敏感 payload；详情接口按权限返回
   脱敏数据。

### 阶段 E：测试与发布

1. 补 TokenProvider、TokenManager、静态 Header、响应体/Header 更新、401 刷新和并发隔离单测。
2. 对四个 Adapter 使用 `httpx.MockTransport` 做协议级测试，不依赖业务 View 才能验证 wire contract。
3. 每条链补：参数错误、外系统 HTTP 错误、业务码错误、超时、脱敏、幂等和真实模式配置测试。
4. 增加前端 submission builder、结果解析、轮询终止、取消和陈旧 context 测试。
5. 扩展架构检查，禁止 `apps/integrations/**` 导入 `apps/product_data/**`。
6. 在内网预发布环境验证 RabbitMQ、Worker 队列、Secret 注入、Token 轮换和日志脱敏后再切真实模式。

## 5. 预计修改文件

以下是按建议方案预计涉及的文件，不表示必须一次性全部修改。

### 5.1 公共后端基础设施

```text
Alkaid-python/apps/integrations/auth.py
Alkaid-python/apps/integrations/contracts.py
Alkaid-python/apps/integrations/executor.py
Alkaid-python/apps/integrations/http.py
Alkaid-python/apps/jobs/http.py
Alkaid-python/apps/jobs/models.py                    # 若增加幂等/同步审计字段
Alkaid-python/apps/jobs/services.py
Alkaid-python/apps/jobs/dispatch.py
Alkaid-python/apps/jobs/migrations/*.py              # 仅数据库结构变化时
Alkaid-python/config/settings/base.py
Alkaid-python/config/settings/server.py
Alkaid-python/.env.example
Alkaid-python/.env.server.example
Alkaid-python/scripts/check_architecture.py
```

### 5.2 产品申请

```text
Alkaid-python/apps/product_data/product_applications/views.py
Alkaid-python/apps/product_data/product_applications/schemas.py
Alkaid-python/apps/product_data/product_applications/tasks.py
Alkaid-python/apps/product_data/product_applications/services.py
Alkaid-python/apps/integrations/mock_product/client.py
Alkaid-python/apps/integrations/mock_product/adapters/application.py
Alkaid-python/apps/integrations/mock_product/api/*.py
Alkaid-python/apps/integrations/mock_product/models/*.py
Alkaid-react/src/pages/ProductApplyPage/api/productApplicationApi.ts
Alkaid-react/src/pages/ProductApplyPage/hooks/useProductApplyJobs.ts
```

### 5.3 申请链接

```text
Alkaid-python/apps/product_data/application_links/views.py
Alkaid-python/apps/product_data/application_links/schemas.py
Alkaid-python/apps/product_data/application_links/tasks.py
Alkaid-python/apps/product_data/application_links/services.py
Alkaid-python/apps/integrations/application_link/adapter.py
Alkaid-python/apps/integrations/application_link/api.py
Alkaid-python/apps/integrations/application_link/models.py
Alkaid-python/apps/product_data/catalog.py
Alkaid-react/src/pages/ApplicationLinkGeneratorPage/config/applicationLinkConfig.ts  # 预计删除/降级
Alkaid-react/src/pages/ApplicationLinkGeneratorPage/api/applicationLink.ts
Alkaid-react/src/pages/ApplicationLinkGeneratorPage/hooks/useApplicationLinkForm.ts
Alkaid-react/src/pages/ApplicationLinkGeneratorPage/model/submission.ts
Alkaid-react/src/pages/ApplicationLinkGeneratorPage/model/types.ts
```

### 5.4 业务准入

```text
Alkaid-python/apps/product_data/business_access/views.py
Alkaid-python/apps/product_data/business_access/schemas.py
Alkaid-python/apps/product_data/business_access/tasks.py
Alkaid-python/apps/product_data/business_access/services.py
Alkaid-python/apps/integrations/business_access/adapter.py
Alkaid-python/apps/integrations/business_access/api.py
Alkaid-python/apps/integrations/business_access/models.py
Alkaid-react/src/pages/BusinessAccessPage/api/businessAccess.ts
Alkaid-react/src/pages/BusinessAccessPage/hooks/useBusinessAccess.ts
Alkaid-react/src/pages/BusinessAccessPage/types.ts
```

### 5.5 核实审批

```text
Alkaid-python/apps/product_data/verification_approval/views.py
Alkaid-python/apps/product_data/verification_approval/schemas.py
Alkaid-python/apps/product_data/verification_approval/services.py
Alkaid-python/apps/product_data/verification_approval/tasks.py          # 若迁入 Job，新增
Alkaid-python/apps/integrations/verification_approval/adapter.py
Alkaid-python/apps/integrations/verification_approval/api.py
Alkaid-python/apps/integrations/verification_approval/models.py
Alkaid-react/src/pages/VerificationApprovalPage/api/verificationApproval.ts
Alkaid-react/src/pages/VerificationApprovalPage/hooks/useVerificationApproval.ts
Alkaid-react/src/pages/VerificationApprovalPage/types.ts
```

### 5.6 测试

```text
Alkaid-python/tests/test_api.py
Alkaid-python/tests/test_business_features.py
Alkaid-python/tests/test_http_client.py
Alkaid-python/tests/test_jobs.py
Alkaid-python/tests/test_runtime_mode.py
Alkaid-python/tests/test_auth.py                              # 建议新增
Alkaid-python/tests/integrations/test_*_adapter.py            # 建议按系统新增
Alkaid-react/src/pages/**/__tests__/*                         # 建议新增
```

## 6. 仍然无法确认的问题

以下问题无法从仓库代码中得到答案，实施前必须向外系统负责人、内网运维或业务方确认：

1. 四个真实外系统各自使用固定 Token、登录 Token、OAuth2、Cookie 还是其他认证方式？
2. Token 有效期、刷新接口、刷新响应位置、提前刷新窗口和 401 后允许重试次数分别是什么？
3. Token 应按用户、机构、产品、Job、Worker 还是整个服务共享？是否允许多个 Worker 并发刷新？
4. 内网是否提供 Vault/KMS/配置中心等 Secret 服务？是否允许持久化 refresh token？加密和轮换要求是什么？
5. 真实外系统是否支持幂等 Header；创建申请、失效、推送、核实操作的幂等语义是什么？
6. 核实审批为什么设计为同步？业务是否接受改为 Job，或者是否必须在一个 HTTP 请求内返回结果？
7. 核实审批回传完整 `context` 是真实外系统合同要求，还是仅为 Mock Store 更新状态的临时设计？
8. 核实任务 ID、item ID、action 的允许字符集是什么？是否可能包含 `/`、空格或非 ASCII 字符？
9. 申请链接外系统要求产品代码还是产品显示名称？环境要求 `env-1` 还是“环境1”？
10. 申请链接 `generate_links` 是否可以安全重试？同一 application number 是否保证返回同一链接？
11. 业务准入查询结果、核实任务状态是否应在本系统持久化，还是始终以外系统为唯一事实来源？
12. 内网入口是否已有统一身份认证、授权、CSRF 替代机制、TLS 和操作审计？
13. Job payload 中的敏感信息允许保存多久、谁可以查看、是否需要字段级加密或不可逆脱敏？
14. 前端四个页面是否需要统一支持任务恢复、取消、重试和跨页面查看？
15. `MOCK_PRODUCT_*` 在真实部署中对应的正式外系统名称和正式环境变量命名是什么？

## 7. 现有测试覆盖摘要

| 范围 | 已覆盖 | 主要缺口 |
| --- | --- | --- |
| 产品申请 | Catalog 快照、Mock 五次外调、RabbitMQ 开发回退、生产投递失败 | Token 直接单测、真实 Header、外系统失败分支、重复写幂等 |
| 申请链接 | 太阳码、动态 JSON 必填、两次外调、当前调试日志 | 配置漂移、名称/代码一致性、静态 Token、外调错误、前端测试 |
| 业务准入 | 查询、失效、通知查询、推送完整 Mock 流程 | 各操作错误/审计/脱敏、真实 Token、前端轮询测试 |
| 核实审批 | 查询、领取、核实项、动作、退回、无结果、缺少 context | 外调审计、幂等、并发/陈旧 context、失败和超时、真实 Token |
| 公共 Job | 幂等、恢复、超时协调、晚到结果保护、脱敏、SSE 终止 | 外系统成功后 worker 丢失、跨步骤幂等、权限 |
| 公共 HTTP | form 序列化、Trace、safe retry 与 never retry | Token 更新、401、所有错误分类、Observer 边界 |

## 8. 建议的下一步决策顺序

在开始改代码前，建议按以下顺序获得明确答案：

1. 先拿到四个真实外系统认证与幂等合同。
2. 决定核实审批是否进入统一 Job。
3. 决定稳定产品标识和申请链接配置的唯一来源。
4. 确定内网认证授权、敏感数据存储和日志规范。
5. 再拆分实施批次：Token/幂等基础设施 → 单系统 Adapter → Domain → 前端 → 测试与发布。
