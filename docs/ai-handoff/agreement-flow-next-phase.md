# 查询协议与阅读协议：代码顺序流程下一阶段方案

## 1. 基准与目标

- Repository：`hero233-li/Alkaid`
- Working branch：`agent/code-flow-refactor`
- 当前分支已完成：申请链接功能改为 `ApplicationLinkFlow.execute()` 中的 Python 方法顺序编排。
- 下一阶段目标：把产品申请中的“查询协议、阅读协议、Token、申请链接、Session”等步骤改为同样的代码顺序流程。

本阶段的核心约束：

1. JSON 只保存产品配置、固定请求报文和业务参数；
2. JSON 不保存 `steps`、`nextStep`、Handler 类名或方法调用顺序；
3. 流程执行顺序必须由 Python Flow 的 `execute()` 明确表达；
4. 不建立通用 WorkflowRunner、StepRegistry、反射式 Handler 系统；
5. 不为每个接口创建一个 Service；
6. 不虚构尚未确认的真实协议字段、签名算法、Token 路径或响应结构。

## 2. 当前仓库事实

当前远程分支中尚不存在真实的：

- `query_agreement`；
- `read_agreement`；
- `CJDK-JYRC/workflow.json`；
- `requests/agreement.json`；
- CJDK-JYRC 真实外系统 Adapter。

现有产品申请仍执行旧的 Mock 链路：

```text
product_applications.tasks.execute_product_application
  -> run_job_task
  -> product_applications.services.run_product_application
  -> _run_mock_product_flow
  -> MockProductApplicationAdapter
  -> login
  -> check_product
  -> rotate_token
  -> submit_application
  -> audit
```

现有通用基础设施已经包含：

- `EndpointExecutor`：统一 HTTP 执行、业务码校验和 Token 更新；
- `FlowTokenProvider`：单次 Job attempt 内可变 Token；
- `StaticTokenProvider`：固定 Token；
- `TokenManager`：根据 EndpointSpec 注入和更新 Token；
- `JobHttpCallObserver`：记录外系统请求审计；
- `HttpClient`：统一超时、重试和 transport。

这些基础设施应复用，不重新实现。

## 3. 推荐放置位置

沿用当前 feature-local 结构：

```text
apps/product_data/product_applications/
├── context.py
├── flow.py
├── schemas.py
├── services.py
├── tasks.py
└── views.py
```

真实外系统按系统与业务域组织：

```text
apps/integrations/cjkd_jyrc/
├── api/
│   ├── agreement.py
│   ├── application_link.py
│   └── session.py
├── adapters/
│   ├── agreement.py
│   ├── application_link.py
│   └── session.py
├── models/
│   ├── agreement.py
│   ├── application_link.py
│   └── session.py
├── raw_messages/
│   ├── agreement.json
│   ├── application_link.json
│   └── session.json
├── client.py
├── messages.py
└── mock_transport.py
```

第一阶段只实现已确认协议，不要一次性创建所有空文件。若当前只具备协议查询和协议阅读的真实报文，则只建立 `agreement` 域文件。

## 4. 产品配置如何引用流程

产品 JSON 可以保存一个稳定的流程代码，但不能保存流程步骤：

```json
{
  "features": {
    "workflow": "cjkd_jyrc_application_v1"
  }
}
```

禁止配置：

```json
{
  "steps": [
    "query_agreement",
    "read_agreement",
    "get_token"
  ]
}
```

`CatalogFeatures` 可新增一个可选的 `workflow` 字段，并冻结到 `ProductExecutionSnapshot.workflow_code`。这只是选择哪个 Python Flow，不决定 Flow 内部步骤。

任务边界采用显式、很小的映射：

```python
PRODUCT_APPLICATION_FLOWS = {
    "cjkd_jyrc_application_v1": CjkdJyrcApplicationFlow,
}
```

不使用字符串反射或动态 import。未知流程代码必须明确报配置错误。

## 5. ProductApplicationContext

在 `product_applications/context.py` 中建立 feature-local Context，只保存步骤间真实共享的数据：

```python
@dataclass
class ProductApplicationContext:
    job: Job
    submission: ProductApplicationSubmission
    execution_snapshot: ProductExecutionSnapshot

    agreement_query: AgreementQueryResult | None = None
    agreement_read: AgreementReadResult | None = None
    application_links: ApplicationLinks | None = None
    session: ApplicationSession | None = None
    result: dict[str, Any] | None = None
```

是否保存 Token：

- Token 继续由 `FlowTokenProvider` / `TokenManager` 管理；
- 不把 Token 明文写入 Job payload、Job result 或普通日志；
- Context 默认不需要复制保存 Token；
- 若业务逻辑必须判断 Token 版本，只保存版本号，不保存 Token 值。

Context 中禁止出现：

- `steps`；
- `current_step`；
- `next_step`；
- `handler_name`；
- 万能 `data: dict`；
- 其他菜单字段。

## 6. Python Flow 如何表达顺序

建议建立：

```python
class CjkdJyrcApplicationFlow:
    def execute(self, *, job, submission, snapshot, progress=None):
        context = self.create_context(job, submission, snapshot)

        self.query_agreement(context)
        self.read_agreement(context)
        self.generate_application_link(context)
        self.create_session(context)
        self.submit_application(context)

        return self.build_result(context)
```

上面只是目标形态。真实顺序必须以已确认的内网接口协议为准；若 Token 实际在某一步获取或更新，由对应 EndpointSpec 的 `token_update` 描述，不要再增加一个只为搬运 Token 的 Service。

若查询协议的响应产生 Token：

```python
QUERY_AGREEMENT = EndpointSpec(
    ...,
    token_update=TokenUpdateSpec(
        provider=CJDK_FLOW_PROVIDER,
        source=TokenSource.RESPONSE_BODY,
        path="已确认的真实响应路径",
    ),
)
```

若阅读协议需要 Token：

```python
READ_AGREEMENT = EndpointSpec(
    ...,
    auth=AuthSpec(
        provider=CJDK_FLOW_PROVIDER,
        header="已确认的真实 Header",
        prefix="已确认的真实前缀",
    ),
)
```

若阅读协议会刷新 Token，同时配置 `auth` 和 `token_update`。不要在 Flow 中手工解析 Header 或拼 Authorization。

## 7. 查询协议与阅读协议的职责

### Agreement Adapter

业务方法建议保持清晰：

```python
class AgreementAdapter:
    def query_agreement(self, request: AgreementQueryInput) -> AgreementQueryResult:
        ...

    def read_agreement(self, request: AgreementReadInput) -> AgreementReadResult:
        ...
```

Adapter 负责：

- 从 `raw_messages/agreement.json` 获取固定供应商报文副本；
- 对动态字段进行显式赋值；
- 调用共用 `client.execute(...)`；
- 返回语义化结果模型。

Adapter 不负责：

- Job 状态；
- Celery；
- 决定下一步；
- 产品页面校验；
- 把 Token 写入数据库；
- 根据 JSON steps 调度。

### agreement.json

`raw_messages/agreement.json` 只保存固定报文主体，例如：

```json
{
  "query_agreement_v1": {
    "REQ_HEAD": {},
    "REQ_BODY": {
      "request": {}
    }
  },
  "read_agreement_v1": {
    "REQ_HEAD": {},
    "REQ_BODY": {
      "request": {}
    }
  }
}
```

动态字段必须在 Adapter 中显式赋值。禁止在 JSON 中放 URL、私钥、Token、步骤顺序或 Python 类名。

## 8. Task、Flow、Service、Adapter 边界

### Task

保留现有：

- `@shared_task` 配置；
- `run_job_task`；
- Job 生命周期；
- 超时；
- 进度；
- 统一异常处理。

Task 只解析 Job 所需的稳定输入并调用 Flow。

### Flow

负责：

- 按 Python 方法顺序编排；
- 维护 Context；
- 在步骤之间传递语义结果；
- 上报业务进度。

### Service

保留：

- 产品参数校验；
- snapshot 解析；
- 流程代码选择；
- 最终业务结果组装中可复用的纯业务函数。

不要为 `query_agreement`、`read_agreement` 各创建一个 Service。

### Adapter / Client

负责：

- 外系统协议；
- 请求报文；
- Token 注入与更新；
- HTTP；
- mock/real transport；
- JobApiCall 审计。

## 9. 与当前 MockProduct 链路的迁移关系

不要直接删除 `_run_mock_product_flow()`。

建议迁移步骤：

1. 先新增 CJDK-JYRC 协议 Adapter 和独立测试；
2. 新增 `CjkdJyrcApplicationFlow`；
3. 产品配置为目标产品设置 `features.workflow`；
4. `run_product_application()` 根据冻结的 `workflow_code` 选择 Flow；
5. 其他未迁移产品继续走现有 Mock Flow；
6. 目标产品在 mock 模式走 CJDK-JYRC mock transport；
7. 内网 real 模式验证通过后，再评估旧 Mock 流程是否仍有调用方。

不允许一次性把所有产品切到未验证的真实流程。

## 10. 必须先确认的真实协议资料

在实现真实接口前，必须从内网样例确认：

### 查询协议

- HTTP method；
- URL/path；
- Content-Type；
- 外层 `payload`、`req`、`biz` 的准确结构；
- env、projectId、appid、traceNo 等字段位置；
- 响应业务码路径和成功值；
- 协议列表、协议编号、版本等响应字段；
- 是否返回 Token，Token 位于 body 还是 header；
- 是否允许安全重试。

### 阅读协议

- 输入依赖查询协议的哪些字段；
- 是否逐条阅读或批量阅读；
- 是否存在循环、顺序或幂等要求；
- 是否需要查询协议返回的 Token；
- 是否刷新 Token；
- 响应业务码路径；
- 阅读完成的确认字段；
- 是否允许安全重试。

无法确认的字段必须显式标记为未实现，不能猜测。

## 11. 第一批验收测试

至少覆盖：

1. 产品配置 workflow code 被正确冻结进 snapshot；
2. 未知 workflow code 明确失败；
3. Python Flow 的查询协议步骤先于阅读协议步骤；
4. 查询协议响应 Token 能被后续阅读协议自动使用；
5. 阅读协议刷新 Token 时版本递增；
6. Token 不出现在 Job result 和日志；
7. 查询协议业务失败时后续步骤不执行；
8. 阅读协议业务失败时后续申请步骤不执行；
9. 每个外系统调用产生准确的 JobApiCall；
10. mock 模式端到端成功；
11. 未迁移产品仍能走旧 Mock Flow；
12. `python manage.py check`、migration drift、完整相关测试通过。

## 12. 本阶段明确不做

- 不创建整体步骤 `workflow.json`；
- 不创建通用 RequestExecutor 的 JSON Runner；
- 不用 JSON 循环执行阅读协议；
- 不用字符串 Handler 分派；
- 不修改数据库模型；
- 不在日志中打印 Token、身份证、手机号或完整敏感报文；
- 不在真实协议未确认时编造实现；
- 不同时改造所有菜单。

## 13. 推荐提交拆分

```text
1. refactor: add product application workflow selection
2. feat: add agreement query and read integration
3. refactor: add code-ordered cjkd jyrc application flow
4. test: cover agreement token and flow ordering
5. docs: report agreement flow implementation
```

每个提交都必须保持可导入；最终分支必须通过 Django check 和相关测试。