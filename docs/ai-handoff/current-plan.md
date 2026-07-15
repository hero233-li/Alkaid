# 申请数据生成、卡状态处理、贷款状态处理当前调用链调查与实施方案

生成日期：2026-07-14
调查范围：申请数据生成、卡状态处理、贷款状态处理，以及它们复用的 Job/Celery 基础设施。

## 一、当前真实调用链

### 1. 申请数据生成

```text
菜单 /product-data/application-data
→ ApplicationDataGeneratorPage
→ submitApplicationData()
→ POST /api/product-data/tools/application-data/generate
→ application_data.views.generate_application_data
→ ApplicationDataSubmission（Pydantic Schema）
→ create_job(kind=application_data.generate)
→ transaction.on_commit → jobs.dispatch.enqueue_job
→ RabbitMQ
→ execute_application_data_task
→ execute_application_data_generation
→ integrations.application_data.generator.generate_application_record
→ 姓名/身份证/银行卡/手机/公司名/统一社会信用代码生成
→ Job.result.records
→ 前端轮询 GET /api/jobs/{id}
→ 表格、复制、二维码或 CSV
```

### 2. 卡状态处理

```text
菜单 /product-data/card-status
→ CardStatusProcessingPage
→ submitCardSearch / submitCardAction
→ POST /api/product-data/tools/cards/search
   或 /tools/cards/{cardNo}/actions/{action}
→ card_status.views
→ CardSearchSubmission / CardActionSubmission
→ create_job(kind=card_status.search|action)
→ RabbitMQ → execute_card_status_task
→ card_status.services.execute_card_status
→ CardStatusAdapter
→ CardMockStore
→ Job.result.cards 或 Job.result.actionResult
→ 前端轮询并更新卡片余额/密码结果
```

### 3. 贷款状态处理

```text
菜单 /product-data/loan-status
→ LoanStatusProcessingPage
→ submitLoanSearch / submitLoanAction
→ POST /api/product-data/tools/loans/search
   或 /tools/loans/{contractNo}/actions/{action}
→ loan_status.views
→ LoanSearchSubmission / LoanActionSubmission
→ create_job(kind=loan_status.search|action)
→ RabbitMQ → execute_loan_status_task
→ loan_status.services.execute_loan_status
→ LoanStatusAdapter
→ LoanMockStore
→ Job.result.cards 或 Job.result.actionResult
→ 前端轮询
→ 合同、额度、凭证、还款计划及操作结果展示
```

三个功能均复用：

```text
Job / JobLog / JobApiCall
jobs.dispatch
Celery 自动发现入口 apps.product_data.tasks
GET /api/jobs/{id}
```

## 二、各层当前职责

### 前端请求入口

- `ApplicationDataGeneratorPage`：收集环境、日期、年龄、性别、柜员、主体类型和数量；展示生成结果。
- `CardStatusProcessingPage`：按环境和客户号查卡，执行存钱、取现、转账及密码重置。
- `LoanStatusProcessingPage`：按环境和客户号查贷款，展示合同/额度/凭证/还款计划并执行贷款操作。
- 三个 API 均使用公共 `createWorkflowHeaders()`，兼容没有 `crypto.randomUUID()` 的内网 HTTP 页面。
- 前端只创建 Job 和轮询，不直接调用 Mock 或真实外系统。

### View

- 解析并校验 JSON、路径参数、幂等键和 Trace ID。
- 创建带 operation snapshot 的 Job。
- 只在事务提交后投递 Celery，不执行具体业务。
- 返回 `202 + Job`，同幂等请求返回已有 Job。

### Serializer / Schema

项目没有使用 DRF Serializer；该职责由 Pydantic Schema 承担：

- `ApplicationDataSubmission`：日期、年龄、性别、主体类型和 1–100000 数量约束。
- `CardSearchSubmission` / `CardActionSubmission`：卡查询与资金/密码操作字段约束。
- `LoanSearchSubmission` / `LoanActionSubmission`：贷款查询和合同操作约束。
- 所有 HTTP 字段使用 camelCase，Python 内部使用 snake_case。

### Task

- 标记 Job running、检查排队截止时间和取消状态。
- 更新进度，调用所属 Service，保存 success/failed/timed_out。
- 三个 Task 均独立注册到 Celery 自动发现入口。
- 卡和贷款写操作不使用 Broker 自动重投；对应 action Job 禁止通用 retry。

### Service

- 只负责 operation 分派和业务结果组装。
- 不解析 HTTP，不创建 Job，不拼 Celery 参数。
- 申请数据 Service 生成 records；卡/贷款 Service 调用各自 Adapter。

### 数据库模型

- 没有新增业务表或 migration。
- `Job` 保存 kind、payload、execution snapshot、进度、结果和错误。
- `JobLog` 保存任务阶段日志。
- `JobApiCall` 保留给真实 HTTP 外系统审计；当前三个 Mock 工具没有伪造 HTTP 调用，因此不会产生虚假的 JobApiCall。

### 外系统调用位置

- 申请数据：`apps/integrations/application_data/generator.py`，纯确定性 Mock 数据生成器。
- 卡状态：`apps/integrations/card_status/adapter.py` → `mock_store.py`。
- 贷款状态：`apps/integrations/loan_status/adapter.py` → `mock_store.py`。
- 当前只有 Mock 实现；`EXTERNAL_SYSTEM_MODE=real` 时卡/贷款 Adapter 明确报未配置，不会静默 Mock。

### 现有测试

- `tests/test_product_data_mock_tools.py`：
  - 实际生成 100000 条并验证姓名、身份证、银行卡、手机号、公司名、信用代码分别不重复；
  - 验证统一社会信用代码校验位；
  - 验证三个功能均通过真实 Job/Task 链路执行；
  - 验证卡存款和贷款冻结 mutation。
- `tests/test_runtime_mode.py`：验证新增 Task 非 Eager 自动发现注册。
- `tests/test_jobs.py`：验证 Task 重投配置和非幂等 Job retry 策略。
- 前端三个新增 API 测试验证请求序列化、卡片 URL 和独立贷款 URL。

## 三、当前存在的问题

1. 卡和贷款的 Mock mutation 状态保存在 Worker 进程内存中；多个 Worker/多进程部署时状态不共享，仅适用于单 Worker Mock 开发。
2. 单次返回十万条会令 `Job.result` JSON、接口响应和浏览器表格非常大。算法支持十万条唯一，但生产式大批量应改为文件流或对象存储结果。
3. 申请数据使用固定行政区划样例和 Mock 姓名词库，不代表真实客户数据分布。
4. 卡状态和贷款状态没有真实外系统协议、URL、认证、报文和返回模型，当前不能实现 real Adapter。
5. 三个后端 config 接口已经存在，但前端仍保留少量环境、柜员和动作展示配置；真实配置源确定后应继续后端化。
6. 贷款前端保留了早期“模拟流程中断/继续处理”的展示代码，而新的非幂等安全策略不允许 action Job 通用重试；该入口目前不会被后端触发，后续可删除 UI 遗留。
7. API 当前没有应用层认证和细粒度授权，部署依赖网关保护。

## 四、建议修改方案

### 已实施

1. 三个功能各自拥有 View、Schema、Task、Service、URL，不再挂靠通用 product_data handler。
2. 贷款状态从卡片 `/tools/cards/*` 拆到 `/tools/loans/*`。
3. 前端统一公共 API Client 和兼容请求 ID。
4. mutation 返回统一为 `result.actionResult`。
5. Mock 数据使用 sequence 映射，不通过随机碰撞重试保证唯一。
6. 公司名称由两个词语加“公司”或“个体”组成。
7. 统一社会信用代码按截图字符集、17 位权重和模 31 算法生成校验位。
8. 不新增数据库表，复用 Job 基础设施。

### 后续建议

1. 真实外系统协议到位后，仅替换 Adapter 后面的实现，保持 View/Task/Service/API 不变。
2. 十万条真实使用场景改为生成 CSV 文件，Job.result 只保存文件元数据和受控下载地址。
3. 若 Mock 需要多 Worker 一致状态，使用 Redis 或专用测试数据库；不要继续依赖进程内字典。
4. 后端 config 成为环境、柜员和动作配置的唯一来源后，再删除前端本地常量。
5. 删除贷款前端未生效的模拟中断/继续处理 UI，除非真实外系统提供可安全恢复的幂等工作流协议。

## 五、预计/实际修改文件

### 后端新增

- `apps/product_data/application_data/{views,schemas,tasks,services,urls}.py`
- `apps/product_data/card_status/{views,schemas,tasks,services,urls}.py`
- `apps/product_data/loan_status/{views,schemas,tasks,services,urls}.py`
- `apps/integrations/application_data/generator.py`
- `apps/integrations/card_status/{adapter,models,mock_store}.py`
- `apps/integrations/loan_status/{adapter,mock_store}.py`
- `tests/test_product_data_mock_tools.py`

### 后端修改

- `apps/product_data/urls.py`
- `apps/product_data/tasks.py`
- `apps/jobs/dispatch.py`
- `apps/jobs/services.py`
- `config/settings/base.py`
- `.env.example`、`.env.server.example`
- `apps/product_data/README.md`
- `tests/test_runtime_mode.py`、`tests/test_jobs.py`

### 前端修改

- 三个页面的 `api/*.ts`
- 申请数据生成数量输入和本地配置
- 贷款状态 Hook 的独立贷款 endpoint 与统一 actionResult 映射
- 删除三个重复的页面级 Axios Client
- 新增三个 API 运行时测试

### 文档

- `docs/API.md`
- `docs/ai-handoff/current-plan.md`

## 六、仍然无法确认的问题

1. 卡状态真实外系统各 action 的 URL、认证、请求报文、业务码和幂等能力。
2. 贷款真实外系统的合同、额度、凭证、还款计划模型以及操作恢复协议。
3. 十万条是要求单批生成并在页面显示，还是要求长期累计唯一；当前实现保证单批十万及基于 Job ID 的大范围序列唯一。
4. 姓名和公司词库是否有内网指定数据源或禁用词清单。
5. 身份证行政区划是否需要读取权威完整地区库。
6. 卡号是否需要指定 BIN、卡种和真实发卡行 Luhn 规则。
7. 统一社会信用代码前两位登记管理部门/机构类别和行政区划是否需要真实业务配置；当前校验位算法与截图一致，但前缀为 Mock 规则。
8. Mock mutation 是否必须跨多 Worker、重启后保持状态；若必须，需要用户授权新增持久化或缓存依赖。
