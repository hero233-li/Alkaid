找到了，文件路径是：

`docs/ai-handoff/current-plan.md`

标题是《四个产品数据功能当前调用链调查与建议方案》。我已经没有直接接受文档结论，而是重新对照了当前分支里的 View、Task、Service、Adapter、Job、Catalog、前端配置和提交逻辑。

## 总体结论

我的判断是：

> **当前主调用链整体合理，不需要推翻重构。`current-plan.md` 作为“现状调查报告”质量不错，但如果把阶段 A～E 全部当成本次实施范围，就明显扩大需求了。**

申请链接现在的链路：

```text
前端
→ ApplicationLink View
→ 创建 Job
→ Celery Task
→ ApplicationLink Service
→ ApplicationLink Adapter
→ EndpointExecutor
→ HttpClient
→ 外系统
```

这个方向是正确的。View 负责 HTTP 和创建 Job，Task 负责异步状态，Service 负责业务编排，Adapter 负责外系统协议，没有出现“View 直接调外系统”或者“Task 填长报文”的问题。

真正需要收口的是下面几个具体问题，而不是统一重做四条业务链。

# P0：必须修改

这里我区分一下：

* 前三项建议本分支处理；
* 第四项至少要在真实客户数据上线前处理。

## P0-1：删除 Adapter 对 ProductCatalog 的反向依赖和原始报文日志

这是目前最明确的架构错误。

`ApplicationLinkAdapter` 位于：

```text
apps/integrations/application_link/
```

但它反向导入了：

```python
from apps.product_data.catalog import load_product_catalog
```

然后为了打印调试信息，又读取产品配置、地区配置和完整请求报文。

依赖方向变成了：

```text
product_data Service
        ↓
Integration Adapter
        ↓
ProductCatalog
        ↑
又回到 product_data
```

问题不只是“不优雅”。

假设真实外系统本来可以正常调用，但 Catalog 加载或者调试日志准备失败，外系统调用也会被一起阻断。

并且 `request_body` 可能包含手机号、证件号、企业信息。项目已经有统一的 `JobHttpCallObserver`，会递归脱敏并限制 Body 大小，不需要 Adapter 再打印一份原始报文。

建议直接：

```text
删除 adapter.py 中：

load_product_catalog
application_link_request_body
application_link_product_config
application_link_product_locations
```

同时删除 `test_api.py` 对这些临时日志的断言。现在测试已经和调试实现绑定了。

需要看配置时，在 Service 层打印经过脱敏的少量路由信息，例如：

```text
productCode
environmentCode
category
catalogVersion
```

不要打印完整业务报文。

---

## P0-2：产品和环境必须统一使用稳定代码

现在存在三种状态。

前端配置使用：

```typescript
产品A
环境1
```

提交时直接把产品显示名称发送给后端。

后端 ProductCatalog 实际已经定义：

```json
{
  "code": "product-a",
  "name": "产品A"
}
```

环境也已经有：

```json
{"label": "环境1", "value": "env-1"}
```

但 Catalog 为兼容旧入口，同时接受：

```text
product-a
产品A
```

申请链接 Service 又把前端传来的原字符串直接冻结进 Snapshot，并继续发送给外系统。

因此现在可能出现：

```text
页面提交：产品A
测试提交：product-a

Job.product：
有时是 产品A
有时是 product-a

外系统 product：
有时是 产品A
有时是 product-a
```

Mock 可以兼容，不代表真实接口可以兼容。

建议统一：

```text
UI 显示：
产品A
环境1

表单真实值：
product-a
env-1

Job：
product-a
env-1

Snapshot：
product-a
env-1

外系统：
product-a
env-1
```

前端 Select 改为：

```typescript
{
  label: '产品A',
  value: 'product-a',
}
```

环境同理。

后端可以暂时继续接受显示名称，但只作为 HTTP 边界兼容。进入 Job 前必须规范化为稳定代码。

这个调整不需要改数据库。

---

## P0-3：两次外系统调用必须处理“部分成功”和重复执行

申请链接不是一次调用，而是：

```text
第一次：
创建申请
→ 得到 application_no

第二次：
根据 application_no 生成链接
```

当前 Task 开启：

```python
acks_late=True
reject_on_worker_lost=True
```

当前系统的 `X-Idempotency-Key` 只保证“不重复创建本地 Job”。

它不能解决这种情况：

```text
1. 外系统成功创建申请 APP-001
2. Worker 在本地保存结果前断开

或者：

1. 创建申请成功 APP-001
2. 生成链接失败
3. 用户点击 Job 重试
4. 再次创建申请 APP-002
```

因此，真实接口接入前必须确认：

> 外系统是否支持幂等键？

支持的话，最小实现是给每一步传稳定幂等键：

```text
{workflow_id}:create-application

{workflow_id}:generate-link
```

Adapter 已经可以通过 `EndpointExecutor` 传自定义 Header，不需要修改数据库。

只有外系统完全不支持幂等时，才考虑持久化中间状态：

```text
application_no
create_application 已完成
generate_link 未完成
```

那时再讨论增加 Job Step 或中间结果字段。

**不要现在直接建新的申请链接业务表。**

---

## P0-4：真实数据上线前，不应在普通 Job 查询中返回完整 payload

当前 Job 本身保存完整 payload，这对于异步执行可以理解。

但是普通 Job 序列化接口又直接返回：

```python
"payload": job.payload
```

申请链接 payload 可能包含：

```text
客户姓名
手机号
证件号码
企业名称
企业代码
动态 JSON
```

当前页面轮询实际上只需要：

```text
id
status
stage
progress
result
errorMessage
```

不需要每 400ms 把完整申请参数重新返回前端。

最小处理不是立刻建设一整套权限平台，而是：

```python
serialize_job(
    job,
    include_payload=False,
)
```

普通轮询默认不返回 payload。

后续确实需要查看原始参数，再做受权限控制的 Job 详情接口。

---

# P1：建议本次修改

## P1-1：申请链接配置改为后端单一来源

现在前端仍然维护：

```typescript
环境
产品
环境对应类别
额外字段
```

后端 ProductCatalog 又维护相同路由：

```json
{
  "environment": "环境1",
  "category": "动态链接",
  "requiredFields": [...]
}
```

目前 Application Link 后端只有 POST 接口，没有配置 GET 接口。

建议增加：

```http
GET /api/product-data/tools/application-links/config
```

返回：

```json
{
  "environments": [
    {
      "label": "环境1",
      "value": "env-1"
    }
  ],
  "products": [
    {
      "label": "产品A",
      "value": "product-a",
      "routes": [
        {
          "environment": "env-1",
          "category": "动态链接"
        }
      ]
    }
  ]
}
```

然后删除前端重复的产品路由配置。

但是：

`合作项目`、`首贷/续贷` 暂时仍然可以放前端，不需要为了“全部统一”扩展 ProductCatalog。

只先消除会影响后端路由判断的重复配置。

---

## P1-2：不要长期保留“顶层客户字段 + requestJson”两个来源

当前 Schema 同时存在：

```python
customerName
customerPhone
customerCertificateNo
customerCompanyName
customerCompanyCode

requestJson
```

验证时又允许：

```text
先找顶层字段
没有再去 requestJson 找
```

但当前前端动态链接实际上只提交：

```json
{
  "requestJson": {
    "customerName": "...",
    "customerPhone": "..."
  }
}
```

这会逐渐变成“大而全的 Submission”。

未来每增加一种动态 JSON 字段，都可能被迫再向顶层 Schema 增加一个可选字段。

建议保留：

```text
公共表单字段：
environment
product
category
cooperationProject
loanType
restoreStatus
spcode

动态业务报文：
requestJson
```

如果需要配置动态 JSON 必填项，可以增加：

```json
{
  "requiredRequestJsonFields": [
    "customerName",
    "customerPhone"
  ]
}
```

而不是继续扩展顶层 Submission。

不过当前三个产品还能运行，这不是阻塞项，可以放 P1。

---

## P1-3：类别路由不要使用 `object + getattr + 默认太阳码`

当前 Adapter 是：

```python
category: object

category_value = getattr(category, "value", category)

endpoint = (
    CREATE_DYNAMIC_LINKS
    if category_value == "动态链接"
    else CREATE_SUN_CODE_LINKS
)
```

这意味着未来出现一个新类别时，可能静默走太阳码。

建议显式处理：

```python
if category == "动态链接":
    endpoint = CREATE_DYNAMIC_LINKS
elif category == "太阳码":
    endpoint = CREATE_SUN_CODE_LINKS
else:
    raise ValueError(...)
```

或者在 Integration models 中增加自己的枚举。

不需要为了这个引入复杂的策略模式。

---

## P1-4：增加依赖方向检查

当前这个问题之所以出现，是因为架构检查只能发现：

```text
Service 直接 import requests/httpx
```

但发现不了：

```text
integrations
→ product_data
```

建议增加一条简单规则：

```text
禁止：

apps/integrations/**
import apps.product_data/**
```

可以防止以后其他 Adapter 再出现相同反向依赖。

---

# P2：后续优化，不进入本次

## P2-1：暂时不要为了统一，把核实审批强行迁入 Job

`current-plan.md` 建议把核实审批 mutation 改成异步 Job。

我不建议现在直接做。

核实审批当前是：

```text
View
→ Service
→ Adapter
→ 外系统
→ 同步返回
```

同步和异步本身没有谁更高级。

如果真实接口：

```text
响应很快
用户必须立即拿到任务最新状态
失败可以立即重试
```

同步反而更简单。

只有业务确认需要：

```text
断线恢复
任务状态持久化
后台继续执行
严格操作审计
取消和重试
```

再迁入 Job。

不要只是为了“四个页面看起来一致”增加 Task、Job 和前端轮询。

---

## P2-2：暂时不要建设通用 Token 刷新框架

现在申请链接使用环境变量中的固定 Token。

如果真实接口合同就是：

```text
固定 Bearer Token
运维定期替换
重启 Worker 生效
```

当前实现足够。

只有确认真实接口存在：

```text
登录接口
access token
refresh token
expires_at
401 刷新
并发刷新
```

再建设 TokenProvider。

不要先做一套可能永远用不到的 Token 平台。

---

## P2-3：暂时不要抽象通用 BaseTask、BaseService

三个异步 Task 的代码确实有重复，但目前每条只有六七十行。

现在抽：

```text
AbstractJobTask
GenericDomainRunner
UnifiedWorkflowExecutor
```

很容易重新走回之前 Workflow/Handler 链路过深的问题。

等业务稳定，并且出现至少三四个真正相同的变化点后再提取。

---

## P2-4：旧 Job 兼容只保留在数据边界

申请链接 Snapshot 还保留：

```python
handler: str | None = None
```

用于旧 Job。

这个兼容目前很小，放在 Schema 边界还可以接受。

但如果这个分支从未在任何环境创建过旧版申请链接 Job，就可以直接删除。

不要为了兼容继续恢复：

```text
Handler Registry
动态 Handler
旧 Workflow
多套执行入口
```

---

# 对你列出的 8 个问题，最终判断

| 检查项               | 我的判断                                   |
| ----------------- | -------------------------------------- |
| 当前调用链             | **合理，不需要推翻**                           |
| View、Task、Service | **职责基本清楚**                             |
| 旧代码兼容复杂度          | `handler` 影响小；产品名称/代码双轨需要收口            |
| 数据库是否修改           | **当前不需要修改**                            |
| 外系统调用位置           | **Adapter → Executor → HttpClient 正确** |
| 异常、日志、事务          | Job 创建和投递边界合理；原始调试日志、部分成功和重复调用需要处理     |
| 增加产品后是否失控         | 当前不会马上失控；配置双源和 Submission 双来源会逐渐失控     |
| 是否有更小实现           | **有，不需要执行 current-plan 的全部阶段**         |

# 我建议本次真正做的最小范围

```text
1. 删除 ApplicationLinkAdapter 中的 Catalog 反向依赖和原始调试日志

2. 增加申请链接 Config GET 接口

3. 前后端统一：
   product-a
   env-1

4. 确认真实外系统请求/响应协议

5. 确认外系统写接口幂等能力
   支持 → 传稳定幂等 Header
   不支持 → 再讨论保存中间步骤

6. 补申请链接协议测试：
   URL
   Header
   请求 Body
   响应映射
   业务错误
   脱敏

7. 不修改 Job 数据模型

8. 不改核实审批执行模型

9. 不建设通用 Token 刷新系统

10. 不抽新的 Workflow / Handler / BaseTask
```

所以这次我的独立结论是：

> **保留当前 View → Job → Task → Service → Adapter 调用链，只修申请链接自身的依赖方向、稳定标识、配置单源和外系统幂等。不要借这次真实接口改造，把四个业务模块全部统一重构。**

---

# 逐条代码验证与实施结果（2026-07-14）

本节是对上述评审意见逐条对照当前代码后的执行记录。实施范围仅限申请链接及其直接依赖的产品目录、架构检查和测试；没有改变产品申请、业务准入、核实审批的执行模型。

## P0-1：接受，已实施

真实代码验证：`apps/integrations/application_link/adapter.py` 确实反向导入 `apps.product_data.catalog`，并在 `DEBUG` 下输出完整请求、产品配置和 locations；`tests/test_api.py` 也把这些临时日志当成正式行为断言。

理由：Adapter 应只处理外部协议，不能依赖产品业务目录；这些日志可能包含客户资料，且和已有 `JobApiCall` 审计重复。

实施结果：

- 删除 Adapter 对 ProductCatalog 的导入和全部临时大对象日志（包括注释中的完整日志方案）。
- 删除 API 测试中的日志断言。
- 保留 `HttpClient` 的正常结构化 INFO 日志，以及 `JobApiCall` / `JobLog` 的脱敏审计。
- 增加不含客户正文和 token 的业务链路日志：`application_link_execution_started`、`application_link_application_created`、`application_link_links_generated`；异常时记录 `application_link_execution_failed`。日志上下文仅包含 Job/workflow/trace 标识、产品、环境、类别和 applicationNo。
- 新增申请链接协议测试，覆盖 URL、Header、Body、响应映射、业务错误和敏感信息掩码。

## P0-2：接受，已实施

真实代码验证：产品申请已经使用 `product-b`、`env-1`，但申请链接页面和产品目录中的申请链接路由仍混用“产品B”“环境1”等显示名称；旧后端又同时允许产品 code 和 name。

理由：显示名称会变化，不应作为 Job payload、快照和外部请求中的稳定标识。

实施结果：

- 产品目录的申请链接 route 环境统一改为 `env-1`、`env-2`、`env-3`。
- 前端选择框显示 label，但提交 `product-a` / `env-1` 等 value。
- HTTP 边界增加兼容归一化：旧调用方仍可提交“产品A”“环境1”，进入 Job 前会转换为稳定 code。
- 新 Job 的 `product`、`payload` 和 `execution_config_snapshot` 均保存稳定 code。
- 产品目录加载时新增环境 code 引用校验，错误配置会在启动/加载阶段失败。

## P0-3：部分接受，本次不实施幂等扩展

真实代码验证：Service 顺序执行“创建申请”和“生成链接”两个写操作；Task 重试或 Worker 中断确实可能导致第一步重复执行。当前外系统协议没有声明支持幂等 Header，也没有可查询第一步结果的接口契约。

理由：风险判断成立，但在未确认外系统能力前，擅自发送自定义幂等 Header 不能保证有效；新增步骤状态表会扩大数据库和恢复语义范围。

本次处理：保留现有 Job 级幂等和顺序执行，不增加 Header、不改数据库。待外系统确认以下任一契约后再实施：

- 支持幂等：明确 Header 名、作用域、有效期及重复响应；
- 不支持幂等：明确 applicationNo 查询/恢复能力，再设计中间状态持久化。

## P0-4：部分接受，本次不实施

真实代码验证：通用 Job 查询目前会序列化 payload，申请链接 payload 可能含客户姓名、手机号和证件号。与此同时，产品申请等页面也依赖同一 Job 详情协议。

理由：数据暴露风险成立，但直接修改共享 `serialize_job` 会影响四个功能及现有前端，且当前没有“列表、轮询、详情、审计”的权限与返回字段契约。

本次处理：不修改共享 Job API。上线真实客户数据前，应单独确认鉴权、轮询最小响应和受控详情接口，再进行跨功能修改。

## P1-1：接受，已实施

真实代码验证：前端 `applicationLinkConfig.ts` 重复维护环境、产品、类别路由和产品 C 额外字段，与后端 JSON 产品目录存在双源。

理由：新增或调整产品时必须同时修改两端，已经存在漂移风险。

实施结果：

- 新增 `GET /api/product-data/tools/application-links/config`。
- 后端从 ProductCatalog 返回环境 label/value、产品 label/value、route category 和 requiredFields。
- 前端启动时获取该配置，并由 route.requiredFields 决定 `restoreStatus`、`spcode` 等显示。
- 前端本地仅保留当前尚无后端目录来源的合作项目和首贷续贷选项。

## P1-2：部分接受，本次不实施字段收敛

真实代码验证：`ApplicationLinkSubmission` 同时保留顶层客户字段和 `requestJson`，校验也会从两个位置取值；当前页面主要提交 `requestJson`，但旧调用方和历史 Job 可能使用顶层字段。

理由：双来源长期不理想，但直接删除字段会破坏旧请求和历史 Job 重放。当前没有外系统最终请求 schema，无法确认哪一种才是稳定契约。

本次处理：维持现有兼容行为，不新增第三种来源。等真实请求模型确认后，在 HTTP 数据边界做一次版本化收敛。

## P1-3：接受，已实施

真实代码验证：Adapter 的 category 类型是 `object`，通过 `getattr` 获取值，并把所有未知类别默认路由到太阳码。

理由：未知输入静默落到写接口可能创建错误业务数据。

实施结果：Adapter 只接受字符串类别，明确匹配“动态链接”和“太阳码”，其他值立即抛出错误；Service 显式传递 Enum 的 value，并新增未知类别测试。

## P1-4：接受，已实施

真实代码验证：现有 `check_architecture.py` 完全跳过 integrations，因此无法发现此次 Adapter → ProductCatalog 的反向依赖。

理由：仅靠约定不能防止同类问题回归。

实施结果：架构检查现在禁止 `apps/integrations/**` 导入 `apps.product_data/**`；当前检查通过。

## P2-1：接受“不修改”的建议，未改代码

真实代码验证：核实审批当前同步执行且没有外部 I/O。没有证据表明它需要 Job、Celery、重试或取消能力。

结论：不迁移核实审批，不扩大本次范围。

## P2-2：接受“不建设”的建议，未改代码

真实代码验证：申请链接 real 模式使用环境配置中的静态 token；当前申请链接 EndpointSpec 没有登录、刷新或响应更新 token 的契约。

结论：不增加通用 Token 刷新框架。待外系统提供 token 获取、过期和刷新协议后再配置现有 TokenManager。

## P2-3：接受“不抽象”的建议，未改代码

真实代码验证：四个功能的同步/异步模式、输出和错误处理不同，当前没有足够重复且稳定的抽象边界。

结论：不新增 BaseTask、BaseService、Workflow 或通用 Handler。

## P2-4：部分接受，保留必要兼容

真实代码验证：新 Job 已保存 execution snapshot；schema 中的 `handler` 只用于读取旧快照，Task 对无快照旧 Job 仍有目录解析回退。

理由：无法证明部署环境不存在历史 Job，直接删除兼容可能使队列或重试任务失败。

本次处理：不新增旧 registry 或运行期 handler 路由；保留 schema 输入兼容和无快照 Job 的 code 归一化回退。

# 最终调用链

## 页面配置链

```text
ApplicationLinkGeneratorPage
  → useApplicationLinkForm.useEffect
  → GET /api/product-data/tools/application-links/config
  → application_links.urls.application_link_config
  → application_links.views.application_link_config
  → application_links.services.get_application_link_config
  → catalog.load_product_catalog
  → reference_data.json + products/product_*.json
  → label/value/routes/requiredFields 返回前端
  → formModel 生成级联选项和额外字段
```

## 申请链接生成链

```text
ApplicationLinkSearchForm.onFinish
  → buildApplicationLinkSubmission（提交 product/env 稳定 code）
  → POST /api/product-data/tools/application-links/generate
  → application_links.views.generate_application_link
  → ApplicationLinkSubmission 校验
  → normalize_submission（兼容旧 label/name，统一为 code）
  → resolve_execution_snapshot + validate_submission
  → jobs.services.create_job（冻结 payload 与 execution snapshot）
  → transaction.on_commit
  → jobs.dispatch.enqueue_job
  → application_links.tasks.execute_application_link
  → Job payload/snapshot 校验
  → application_links.services.generate_application_links
      → application_link_execution_started（安全业务日志）
  → ApplicationLinkAdapter.create_application
  → EndpointExecutor → HttpClient → 外系统 /applications
      → external_http_request + application_link_application_created
  → ApplicationLinkAdapter.generate_links（显式类别路由）
  → EndpointExecutor → HttpClient
      → 外系统 /links/sun-code 或 /links/dynamic
      → external_http_request + application_link_links_generated
  → JobHttpCallObserver（脱敏记录 JobApiCall / JobLog）
  → mark_job_success
  → 前端轮询 GET /api/jobs/{id}
  → 展示 internalUrl / externalUrl
```

# 验证结果

- Python Ruff：通过。
- 架构依赖检查：通过。
- 后端完整测试：`29 passed`。
- 前端 TypeScript + Vite 生产构建：通过；仅有原有 bundle 大小提示。

# 仍需外部确认

1. 外系统两个写接口是否支持幂等；具体 Header、作用域、有效期和重复请求返回语义。
2. 外系统真实 token 的获取、过期、刷新和响应更新协议；当前仅能确认静态配置 token。
3. 真实 `create_application` / `generate_links` 请求响应字段是否与现有 mock schema 完全一致。
4. Job 查询的调用者权限，以及列表、轮询、详情分别允许返回哪些 payload/result 字段。
5. 合作项目和首贷续贷选项的权威数据源；当前仍由前端本地维护。
6. 顶层客户字段与 `requestJson` 的最终唯一外部请求模型，以及旧调用方/历史 Job 的实际保留周期。
