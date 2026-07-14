# 产品数据重构最终实施报告

生成日期：2026-07-14  
实施分支：`agent/job-and-application-link-refactor`

## 一、原需求

本阶段需求覆盖四个产品数据功能的调用链审查，并对确认合理的方案进行有限实施：

1. 产品申请；
2. 申请链接获取；
3. 业务准入；
4. 核实审批。

实际实施重点为申请链接和核实审批：

- 调查前端、View、Serializer/Schema、Task、Service、数据库模型、外系统调用和测试的真实链路；
- 申请链接调用时能够观察真实接口链路，但不在普通终端日志中打印客户原始正文、完整产品配置或 token；
- 移除 ApplicationLinkAdapter 对 ProductCatalog 的反向依赖；
- 统一产品、环境稳定代码，兼容旧中文名称请求；
- 将申请链接环境、产品、类别路由和额外必填字段改为后端单一来源；
- 未知申请链接类别不得默认进入太阳码接口；
- 增加外部协议、脱敏和架构依赖测试；
- 核实审批查询结果提供手动刷新，刷新时整体提交后端返回的 context；
- 单项“完成/取消”后自动刷新；
- 最终将核实审批从同步外系统调用迁移为与另外三个功能一致的 Job + RabbitMQ + Celery 异步链路；
- 保持现有 URL 和请求 Body 尽可能兼容，不进行无关抽象或数据库扩展。

## 二、最终方案

### 2.1 申请链接

- 新增 `GET /api/product-data/tools/application-links/config`，从 ProductCatalog 返回环境 label/value、产品 label/value、routes 和 requiredFields。
- 前端不再重复维护产品、环境及类别路由；合作项目和首贷续贷因缺少权威后端来源，暂时保留本地配置。
- HTTP 边界将旧的“产品A”“环境1”等显示名称归一化为 `product-a`、`env-1` 等稳定代码。
- 新 Job 的 product、payload 和 execution snapshot 均保存稳定代码。
- Adapter 仅负责外部协议，不再导入 `apps.product_data`。
- 类别路由显式匹配“太阳码”和“动态链接”，未知类别立即失败。
- 保留 HttpClient 结构化日志、JobLog 和 JobApiCall 脱敏审计；新增不含客户正文和 token 的业务阶段日志。

### 2.2 核实审批刷新

- 新增内部刷新接口：`POST /api/product-data/verification-approval/{taskId}/refresh`。
- 请求继续使用兼容结构：`{"context": 完整任务上下文}`。
- 外系统适配路径暂定为 `POST /verification/tasks/{taskId}/refresh`。
- 页面查询出任务后显示刷新按钮。
- 单项完成或取消成功后，使用操作返回的最新 context 自动再提交 refresh Job。
- 操作成功但自动刷新失败时保留操作结果，只提示刷新失败，不把原操作误报为失败。

### 2.3 核实审批异步化

- 配置 GET 保持同步，所有会访问外系统的业务操作改为异步 Job：search、claim、return、refresh、item-update、action。
- View 完成参数校验、路径与 context 一致性校验、幂等键/trace ID 解析和 Job 创建。
- Job kind 使用 `verification_approval.<operation>`。
- 新增专属 Celery Task，支持排队超时、取消检查、进度、成功、失败和超时状态。
- Job dispatcher 注册 `verification_approval.*`。
- VerificationApprovalAdapter 改为接收 Job，并通过 JobHttpCallObserver 记录每次外系统调用。
- 前端每次操作先获取 Job ID，再轮询 `/api/jobs/{id}`，最终从 `job.result.task` 更新页面。
- 单项完成/取消后的自动刷新会创建第二个独立 refresh Job。

### 2.4 明确未实施

- 未在外系统协议未确认前增加自定义幂等 Header。
- 未新增申请步骤状态表或其他业务数据库表。
- 未建设通用 token 登录/刷新框架。
- 未删除申请链接顶层客户字段与 requestJson 的历史兼容。
- 未修改共享 Job 查询的 payload 返回策略。
- 未抽象新的 BaseTask、BaseService、Workflow 或 Handler 框架。

## 三、修改文件

### 3.1 申请链接后端与目录

- `Alkaid-python/apps/integrations/application_link/adapter.py`：删除业务目录依赖和原始大对象日志；显式类别路由。
- `Alkaid-python/apps/product_data/application_links/schemas.py`：增加页面配置响应模型。
- `Alkaid-python/apps/product_data/application_links/services.py`：稳定代码归一化、配置生成、路由解析和安全阶段日志。
- `Alkaid-python/apps/product_data/application_links/tasks.py`：旧 Job 兼容归一化及失败日志。
- `Alkaid-python/apps/product_data/application_links/urls.py`：注册配置接口。
- `Alkaid-python/apps/product_data/application_links/views.py`：配置 View 和 Job 前归一化。
- `Alkaid-python/apps/product_data/catalog.py`：校验产品及申请链接环境 code 引用。
- `Alkaid-python/apps/product_data/configs/products/product_a.json`：申请链接环境改为稳定 code。
- `Alkaid-python/apps/product_data/configs/products/product_b.json`：申请链接环境改为稳定 code。
- `Alkaid-python/apps/product_data/configs/products/product_c.json`：申请链接环境改为稳定 code。

### 3.2 核实审批后端与集成

- `Alkaid-python/apps/product_data/verification_approval/tasks.py`：新增核实审批 Celery Task。
- `Alkaid-python/apps/product_data/verification_approval/views.py`：业务接口改为创建异步 Job。
- `Alkaid-python/apps/product_data/verification_approval/services.py`：按 Job operation 执行外系统操作。
- `Alkaid-python/apps/product_data/verification_approval/schemas.py`：增加 operation 和 Job 执行载荷。
- `Alkaid-python/apps/product_data/verification_approval/urls.py`：注册刷新接口。
- `Alkaid-python/apps/integrations/verification_approval/adapter.py`：接入 Job 和 JobHttpCallObserver。
- `Alkaid-python/apps/integrations/verification_approval/api.py`：定义外系统刷新 Endpoint。
- `Alkaid-python/apps/integrations/verification_approval/mock_transport.py`：支持刷新协议和外部状态查询。
- `Alkaid-python/apps/jobs/dispatch.py`：注册 `verification_approval.*` 任务分发。
- `Alkaid-python/config/settings/base.py`：增加核实审批任务超时配置。
- `Alkaid-python/.env.example`：增加 `VERIFICATION_APPROVAL_TIMEOUT_SECONDS` 示例。
- `Alkaid-python/.env.server.example`：增加服务端超时配置示例。
- `Alkaid-python/apps/product_data/README.md`：将核实审批执行方式更新为异步 Job。

### 3.3 前端

- `Alkaid-react/src/pages/ApplicationLinkGeneratorPage/api/applicationLink.ts`：获取后端申请链接配置。
- `Alkaid-react/src/pages/ApplicationLinkGeneratorPage/config/applicationLinkConfig.ts`：删除重复路由配置。
- `Alkaid-react/src/pages/ApplicationLinkGeneratorPage/hooks/useApplicationLinkForm.ts`：加载后端配置。
- `Alkaid-react/src/pages/ApplicationLinkGeneratorPage/index.tsx`：配置加载和错误状态。
- `Alkaid-react/src/pages/ApplicationLinkGeneratorPage/model/formModel.ts`：基于 routes 生成级联表单。
- `Alkaid-react/src/pages/ApplicationLinkGeneratorPage/model/submission.ts`：提交稳定 code。
- `Alkaid-react/src/pages/ApplicationLinkGeneratorPage/model/types.ts`：同步配置类型。
- `Alkaid-react/src/pages/VerificationApprovalPage/api/verificationApproval.ts`：业务请求返回 Job，并增加 Job 轮询。
- `Alkaid-react/src/pages/VerificationApprovalPage/hooks/useVerificationApproval.ts`：统一异步工作流、手动刷新和自动刷新。
- `Alkaid-react/src/pages/VerificationApprovalPage/components/VerificationTaskPanel.tsx`：增加刷新按钮。
- `Alkaid-react/src/pages/VerificationApprovalPage/components/VerificationWorkflowModal.tsx`：展示 Celery Job 真实进度。
- `Alkaid-react/src/pages/VerificationApprovalPage/index.tsx`：接入异步活动状态。
- `Alkaid-react/src/pages/VerificationApprovalPage/types.ts`：增加 Job、operation 和 activity 类型。

### 3.4 测试、架构与文档

- `Alkaid-python/scripts/check_architecture.py`：禁止 integrations 反向导入 product_data。
- `Alkaid-python/tests/test_api.py`：验证申请链接配置、稳定代码、Job 快照和安全日志。
- `Alkaid-python/tests/test_application_link_integration.py`：验证 URL、Header、Body、响应、业务错误和脱敏。
- `Alkaid-python/tests/test_business_features.py`：验证核实审批全部操作通过 Job/Celery 执行及外部调用审计。
- `docs/ai-reviews/application-link-review.md`：评审原文、逐条判断和申请链接实施记录。
- `docs/ai-handoff/final-implementation-report.md`：本最终实施报告。

## 四、最终调用链

### 4.1 申请链接配置

```text
ApplicationLinkGeneratorPage
→ GET /api/product-data/tools/application-links/config
→ View
→ ApplicationLink Service
→ ProductCatalog
→ reference_data.json + product_*.json
→ label/value/routes/requiredFields
→ 前端级联表单
```

### 4.2 申请链接生成

```text
前端提交稳定 product/environment code
→ POST /api/product-data/tools/application-links/generate
→ View + Schema
→ 兼容旧 label/name 并归一化为 code
→ 冻结 execution snapshot
→ create_job
→ RabbitMQ
→ ApplicationLink Celery Task
→ Service
→ ApplicationLinkAdapter.create_application
→ EndpointExecutor → HttpClient → 外系统 /applications
→ ApplicationLinkAdapter.generate_links
→ 外系统 /links/sun-code 或 /links/dynamic
→ JobApiCall / JobLog 脱敏审计
→ Job success
→ 前端轮询并展示链接
```

### 4.3 核实审批

```text
前端查询/领取/退回/刷新/完成/取消/快捷操作
→ 原业务 URL（Body 保持 context 结构）
→ View 校验 Schema、路径、context、幂等键和 trace ID
→ create_job(kind=verification_approval.<operation>)
→ transaction.on_commit
→ jobs.dispatch.enqueue_job
→ RabbitMQ
→ execute_verification_approval_task
→ Job 状态与取消/超时检查
→ Verification Service
→ VerificationApprovalAdapter(Job)
→ EndpointExecutor → HttpClient → 真实外系统
→ JobHttpCallObserver → JobApiCall / JobLog
→ mark_job_success(result={task: ...}) 或 mark_job_failed
→ 前端轮询 GET /api/jobs/{jobId}
→ 读取 result.task
→ 更新页面
```

完成/取消后的自动刷新：

```text
item-update Job 成功
→ 前端采用操作返回 task
→ 自动创建 refresh Job
→ 再次轮询
→ 使用外系统最终 task 覆盖页面状态
```

## 五、数据库变化

- 没有新增或修改 Django Model。
- 没有新增 migration。
- 申请链接和核实审批继续复用现有表：
  - `Job`：持久化 payload、result、状态、进度、trace ID、幂等键和 execution snapshot；
  - `JobLog`：任务阶段和失败记录；
  - `JobApiCall`：外系统 URL、脱敏 Header/Body、响应、耗时及错误。
- 核实审批从同步改为异步后会新增上述表中的运行数据，但不改变表结构。

## 六、测试结果

- 申请链接定向测试：通过。
- 核实审批/业务功能定向测试：`4 passed`。
- 后端完整测试：`29 passed`。
- Python Ruff：通过。
- 架构依赖检查：通过。
- 前端 TypeScript + Vite 生产构建：通过。
- `git diff --check`：通过。
- 前端构建仍有既有 bundle 超过 500 kB 的提示，不影响构建成功。

## 七、已知风险

1. 真实外系统刷新接口按 `/verification/tasks/{taskId}/refresh` 实现，路径、请求字段和返回 schema 仍需以真实接口文档或联调结果确认。
2. 外系统两个申请链接写接口是否支持幂等尚未确认；当前只有入口 Job 级幂等，Worker 在第一步成功后异常仍可能造成外部重复创建。
3. 申请链接和核实审批真实 token 当前来自静态环境变量；登录、过期、刷新及响应更新 token 的契约尚未提供。
4. 通用 Job 详情仍可能返回完整 payload；真实客户数据上线前需确认鉴权，以及列表、轮询、详情的最小字段策略。
5. 顶层客户字段与 requestJson 仍是双来源兼容模型，需在真实外部请求 schema 和旧任务保留期明确后收敛。
6. 合作项目和首贷续贷仍由申请链接前端本地维护，权威数据源尚未确定。
7. 生产/内网部署需要 RabbitMQ 可用，并在发布后重启 Celery Worker 以注册 `execute_verification_approval`；真实模式不会使用本地同步兜底。
8. 当前无法完成 GitHub 发布前置校验：本机未安装 `gh`，且当前沙箱内访问 `github.com` 的 DNS 检查失败。

## 八、Git diff 摘要

生成报告前的工作区统计：

```text
当前分支：agent/job-and-application-link-refactor
跟踪文件：38 files changed
跟踪文件增删：849 insertions(+), 371 deletions(-)
新增实现/测试/评审文件：3 个
  - verification_approval/tasks.py：67 行
  - test_application_link_integration.py：123 行
  - application-link-review.md：854 行
本报告：新增文件
```

按实现域拆分的跟踪文件统计：

```text
申请链接：19 files changed, 331 insertions(+), 164 deletions(-)
核实审批及公共配置：19 files changed, 518 insertions(+), 207 deletions(-)
```

本次差异没有 migration，没有依赖锁文件变化，也没有生成文件进入 Git 状态。

## 九、GitHub 发布状态

- 远端：`git@github.com:hero233-li/Alkaid.git`
- 分支：`agent/job-and-application-link-refactor`
- 当前状态：尚未提交、尚未推送。
- 阻塞原因：GitHub 发布流程要求的 `gh` CLI 未安装；同时当前受限网络环境无法解析 `github.com`。
- 后续动作：安装并登录 `gh` 后，复核本报告和完整 diff，显式暂存本报告列出的文件，提交、推送当前分支并创建草稿 PR。
