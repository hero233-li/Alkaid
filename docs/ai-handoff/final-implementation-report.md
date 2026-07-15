# `0674ad9` 到当前版本审查实施报告

生成日期：2026-07-15

基线版本：`0674ad999ecc6ae102a036ebd09510d0405df018`

当前版本：`4b6f698610fe7174621081fd5e0339664f843e58`

当前分支：`agent/job-and-application-link-refactor`

原审查报告：`docs/ai-reviews/final-implementation-review.md`

## 一、审查结论

从指定基线到当前版本共有 2 个提交：

```text
b1387a6 feat: add async mock data and status tools
4b6f698 refactor: use one-call application link contract
```

差异规模为：

```text
102 files changed, 4396 insertions(+), 871 deletions(-)
```

原审查报告中的主要合并前问题已经完成整改或采取了保守风险缓解策略。当前验证全部通过，且本地 HEAD 与远端跟踪分支一致。

但本次增量审查发现 4 个 P1 和 2 个 P2 新问题，主要集中在新增 Mock 数据/状态工具，而不是原核实审批整改本身。基于这些发现，建议：

- 原审查整改代码可以保留；
- 当前版本可以进入测试环境；
- 新增 Mock 工具应先处理 P1 项，再作为稳定的多 Worker 联调工具使用；
- 申请链接和核实审批接入真实外系统前，仍必须完成外部协议确认。

## 二、新增审查发现

### P1-1：10 万条申请数据一次性驻留内存、写入数据库并通过 Job 详情返回

涉及文件：

- `Alkaid-python/apps/product_data/application_data/schemas.py:22`
- `Alkaid-python/apps/product_data/application_data/services.py:23-38`
- `Alkaid-react/src/pages/ApplicationDataGeneratorPage/api/applicationData.ts:39-46`

接口允许单个 Job 生成 100,000 条记录。Worker 先在 Python list 中构造全部记录，再把完整数组写入 `Job.result`；前端轮询到成功时又通过普通 Job 详情一次性下载完整结果。

风险包括：

- Worker 峰值内存明显上升；
- 数据库 JSON 字段和事务写入体积过大；
- Job 详情序列化、网络响应和浏览器状态再次复制大对象；
- 接口没有批次、分页或导出文件边界，重复提交可形成资源耗尽。

建议把大批量结果改为分批生成并写入文件或专用存储，Job.result 只保存摘要、计数和下载标识；在完成改造前下调单次上限，并增加后端总大小限制。

### P1-2：卡/贷款 Mock 状态是进程内全局变量，与 Celery 多进程执行模型不兼容

涉及文件：

- `Alkaid-python/apps/integrations/card_status/mock_store.py:11-18`
- `Alkaid-python/apps/integrations/loan_status/mock_store.py:11-18`

卡和贷款状态保存在模块级 `CARD_MOCK_STORE` / `LOAN_MOCK_STORE` 的内存字典中。查询 Job 与操作 Job 是两次独立 Celery 投递，可能由不同 Worker 或不同 prefork 子进程执行。

结果可能是：

```text
查询 Job 在 Worker A 创建 Mock 状态
→ 操作 Job 被 Worker B 消费
→ Worker B 内存中没有该卡或合同
→ 返回“请先查询”或“合同不存在”
```

当前测试使用 Eager/同进程执行，因此不能暴露该问题。建议 Mock 状态至少落入共享数据库或 Redis；如果明确只支持单进程开发模式，应在启动配置中强制单 Worker 并在文档和运行时校验中明确限制。

### P1-3：卡转账校验了目标卡号，但执行时完全忽略目标卡

涉及文件：

- `Alkaid-python/apps/product_data/card_status/schemas.py`
- `Alkaid-python/apps/product_data/card_status/services.py:18-24`
- `Alkaid-python/apps/integrations/card_status/mock_store.py:56-66`

`CardActionSubmission` 要求转账时提供 `targetCard`，但 Service 调用 Adapter 时只传源卡、action 和 amount；Mock Store 将 transfer 与 withdraw 作为同一逻辑，仅扣减源卡余额，没有校验、创建或增加目标卡余额。

因此接口会返回“转账成功”，实际行为只是取现。建议把 `target_card` 贯穿 Service、Adapter 和 Store，并增加源卡/目标卡余额双向断言及目标卡不存在测试。

### P1-4：三个新增异步页面重新引入无限轮询

涉及文件：

- `Alkaid-react/src/pages/ApplicationDataGeneratorPage/api/applicationData.ts:35-51`
- `Alkaid-react/src/pages/CardStatusProcessingPage/api/cardStatus.ts:45-53`
- `Alkaid-react/src/pages/LoanStatusProcessingPage/api/loanStatus.ts:51-61`

原审查对核实审批提出的 `while (true)` 风险已经通过 150 秒截止时间和 `AbortSignal` 解决，但本次新增的申请数据、卡状态、贷款状态轮询仍无限执行，页面卸载后也没有主动取消。

如果 Job 长时间无法进入终态或组件已经卸载，浏览器仍会持续请求并尝试更新状态。建议复用已经验证的截止时间和取消模式；不必先抽象完整 Job Client，但至少保持行为一致。

### P2-1：`birthDate` 被接口接受并保存，但生成逻辑完全忽略

涉及文件：

- `Alkaid-python/apps/product_data/application_data/schemas.py:16-20`
- `Alkaid-python/apps/product_data/application_data/services.py:25-31`

请求模型接受 `birthDate`，但身份证生日只由 `currentDate + age + sequence` 计算。调用方传入与 age 不一致的出生日期时不会报错，也不会影响结果。

建议确定唯一权威字段：若 `birthDate` 是用户意图，应直接使用并校验 age；若只需要 age，应从协议和前端表单删除 `birthDate`，避免产生虚假的可配置项。

### P2-2：申请数据配置新增了后端接口，但前端仍维护独立常量

涉及文件：

- `Alkaid-python/apps/product_data/application_data/services.py:41-49`
- `Alkaid-react/src/pages/ApplicationDataGeneratorPage/config/applicationDataConfig.ts:1-10`

后端已提供 environments、companyTypes 和 maxCount，前端仍硬编码同一组值，且 label 已出现差异：后端为“公司/个体”，前端为“91类型/92类型”。

建议前端加载后端配置，仅保留页面默认值，避免以后环境、主体类型或数量上限再次漂移。

## 三、原审查项实施状态

### 3.1 总体统计

| 优先级 | 已实施 | 部分实施/风险缓解 | 按建议不实施 | 合计 |
| --- | ---: | ---: | ---: | ---: |
| P0 | 2 | 1 | 0 | 3 |
| P1 | 3 | 3 | 0 | 6 |
| P2 | 2 | 0 | 2 | 4 |
| 合计 | 7 | 4 | 2 | 13 |

### 3.2 P0 实施情况

#### P0-1：核实审批 Celery Task 自动发现

状态：**已实施**。

- `apps/product_data/tasks.py` 已导入并导出 `execute_verification_approval_task`。
- `tests/test_runtime_mode.py` 增加非 Eager 的默认模块加载和任务注册验证。
- 当前入口还注册了本次新增的申请数据、卡状态和贷款状态 Task。

未完成项：尚未连接真实 RabbitMQ 启动独立 Worker 做端到端消费验证。

#### P0-2：前端直接调用 `crypto.randomUUID()`

状态：**已实施**。

- 新增共享 `createRequestId()` / `createWorkflowHeaders()`。
- 原生 `randomUUID` 不可用时降级到 `getRandomValues`，再降级到时间戳和伪随机值。
- 产品申请、申请链接、业务准入、核实审批以及本次新增页面均改用共享实现。
- 已有无 `crypto.randomUUID()` 环境的运行时测试。

#### P0-3：外系统写操作重复执行

状态：**部分实施，采用保守策略**。

- 外系统 Task 已使用 `acks_late=False`、`reject_on_worker_lost=False`，Worker 丢失时不由 Broker 自动重放。
- 产品申请、申请链接、业务准入 mutation、核实审批 mutation、卡状态和贷款状态 mutation 被列入通用 Job 禁止重试集合。
- 核实审批 refresh 已取消 `RetryMode.SAFE`。
- 申请链接从原来的“创建申请 + 生成链接”两次外部调用收敛为一次 link 调用，原两阶段部分成功问题已消除。

仍未解决：外系统没有确认幂等协议。外部写成功但本地尚未保存成功状态时，系统只能人工核对，不能自动恢复，也不能保证 exactly-once。

### 3.3 P1 实施情况

#### P1-1：API 文档同步

状态：**已实施**。

`docs/API.md` 已补充核实审批异步 Job、刷新接口、申请链接配置、payload 策略、重试限制和当前一次调用的申请链接表单协议。

仓库外调用方是否仍依赖旧同步响应无法通过本仓库确认。

#### P1-2：核实审批刷新真实协议未确认

状态：**部分实施**。

- 完整 context 回传保留；
- 外部刷新请求自动重试已取消；
- 路径仍暂定为 `/verification/tasks/{taskId}/refresh`。

真实路径、请求字段、响应 Schema 和无副作用属性仍待接口文档或联调确认。

#### P1-3：危险失败链测试不足

状态：**部分实施，自动化覆盖已补强**。

新增覆盖包括：

- Celery 自动发现；
- 外系统 HTTP 和业务码失败；
- mutation 失败审计；
- 非幂等 Job retry 拒绝；
- Job 轮询 payload 默认隐藏；
- supplement、approval-submit 和核实项取消；
- 核实审批外系统协议；
- 申请链接太阳码/动态链接的一次调用 URL、五字段表单、响应映射、业务失败和字段冲突。

仍缺真实 RabbitMQ、Worker 未注册、Worker 强杀、跨进程 Mock 状态和外系统成功后进程丢失测试。

#### P1-4：前端运行时行为测试

状态：**已实施原审查要求，但新增页面覆盖仍有限**。

已引入 Vitest、Testing Library 和 jsdom。当前 7 个测试文件、11 个测试通过，覆盖原审查要求的关键行为。新增申请数据、卡状态和贷款状态 API 有基础测试，但未覆盖本报告第二节列出的跨进程状态、大结果和无限轮询风险。

#### P1-5：Job 轮询暴露完整 payload

状态：**部分实施**。

- `GET /api/jobs/{id}` 默认不返回 payload。
- 显式 `includePayload=true` 仍可返回。

当前应用没有细粒度鉴权，真实客户数据上线前应把原始参数查看能力迁移到受权限控制的详情接口，不能只依赖查询参数和网关约定。

#### P1-6：核实审批轮询无截止时间/取消

状态：**已实施**。

核实审批轮询已有 150 秒默认截止时间、`AbortSignal` 和组件卸载取消，取消不会误报为业务失败。新增页面没有沿用该行为，已单列为本报告 P1-4。

### 3.4 P2 实施情况

#### P2-1：抽取共享 Job Client/Hook

状态：**按审查建议不实施**。当前仍保留各功能显式工作流。

#### P2-2：Service 恒真 Context 校验

状态：**已实施**。同源恒真校验已删除，URL 与 context 一致性继续由 View 校验。

#### P2-3：抽取 BaseTask

状态：**按审查建议不实施**。当前业务行为仍在变化，保留显式 Task 更容易审计。

#### P2-4：GitHub 状态过期

状态：**已修正**。当前本地 HEAD 与 `origin/agent/job-and-application-link-refactor` 均为 `4b6f698`，ahead/behind 为 `0/0`。

## 四、两个提交的主要实施差异

### 4.1 `b1387a6`：整改与异步 Mock/状态工具

该提交主要完成：

- 原最终审查报告的 Celery 注册、请求 ID、非幂等重试、payload 最小化、核实审批轮询取消和测试整改；
- 新增申请数据生成 Job；
- 新增卡状态查询与操作 Job；
- 新增贷款状态查询与操作 Job；
- 将新增 Task 接入 dispatcher、自动发现、超时配置和统一前端 API Client；
- 增加后端协议/失败测试和前端运行时测试；
- 更新 API 文档和实施记录。

### 4.2 `4b6f698`：申请链接一次调用协议

该提交主要完成：

- 删除“先创建申请、再生成链接”的两阶段外部调用；
- 每个申请链接 Job 只调用一次 `/links/sun-code` 或 `/links/dynamic`；
- Python 组装并提交 `msg_id`、`sign`、`timestamp`、`REQ_MESSAGE`、`biz_content` 五字段表单；
- `REQ_MESSAGE` 与 `biz_content` 使用同一序列化内容；
- 外层 env/product/category/cooperationProjectId 成为权威路由字段，payload 冲突时拒绝执行；
- 合作项目进入后端 reference data 并下发前端；
- 增加两类请求契约样例、协议测试和 Windows 生命周期脚本改进。

尚未闭环的申请链接真实协议：

1. `sign` 当前只支持静态配置，真实算法或 Java/Jar SDK 尚未接入；
2. timestamp 格式仍需真实接口确认；
3. 两个真实路径、成功码和响应字段仍需联调确认；
4. 内网 Java/Python SDK 或 Jar 不在当前仓库中，无法在本次审查中验证。

## 五、版本与工作区状态

生成报告前：

- 本地 HEAD：`4b6f698`
- 远端跟踪分支 HEAD：`4b6f698`
- ahead/behind：`0/0`
- 工作区：干净

本报告写入后，本地只修改了本报告文件；业务代码仍与当前远端提交一致。

## 六、验证结果

在当前版本上实际执行：

| 验证项 | 结果 |
| --- | --- |
| 后端完整测试 | `42 passed in 9.25s` |
| Python Ruff | 通过 |
| 架构依赖检查 | 通过 |
| 前端 Vitest | `7 files / 11 tests passed` |
| TypeScript + Vite 生产构建 | 通过 |
| `git diff --check 0674ad9..HEAD` | 通过 |

前端构建仍有单个 bundle 超过 500 kB 的告警，不影响构建成功。

## 七、处置建议

### 合并前建议处理

1. 修复卡转账目标卡未参与执行的问题，并补完整行为测试。
2. 为申请数据 100,000 条结果增加分批/文件化方案或先下调上限。
3. 明确卡/贷款 Mock 的单进程限制，或迁移到共享持久化 Store。
4. 为申请数据、卡状态和贷款状态轮询增加截止时间与卸载取消。

### 真实外系统上线前必须处理

1. 确认核实审批 refresh 的真实协议。
2. 确认外系统写操作幂等契约和人工补偿规程。
3. 确认申请链接签名算法、时间戳、真实路径和响应字段。
4. 在 RabbitMQ + 独立 Celery Worker 环境完成注册、消费、超时、取消和 Worker 强杀验证。
5. 为 Job 原始 payload 查看能力增加应用内权限控制。

## 八、最终判定

- 原审查整改实施：**基本完成，P0-3 仍为保守风险缓解而非根治**。
- `0674ad9` 到 `4b6f698` 增量：**功能扩展明显，自动化验证通过，但存在 4 个建议在合并前处理的 P1 问题**。
- 测试环境：**可进入，需知晓 Mock 多进程限制**。
- 真实外系统生产上线：**暂不建议，需先完成外部协议、幂等和 Worker 故障演练**。
