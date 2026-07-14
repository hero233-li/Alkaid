# P0 / P1 / P2 全量整改实施报告（2026-07-15）

## 一、版本口径

- 被审查业务版本：`4b6f698610fe7174621081fd5e0339664f843e58`
- 原审查实施报告提交：`0225a89`
- 本次整改实施代码提交：`5077c92`
- 本报告文档提交：本文件所在提交
- 本次实施状态：已完成本地提交，待人工推送
- 当前分支：`agent/job-and-application-link-refactor`

本报告分别记录业务基线、实施代码提交和报告文档提交，不再把报告提交误写成被审查业务版本。

## 二、总体结论

- P0：4/4 已实施。
- P1：所有本地代码项均已实施；真实外部协议、真实 Broker 故障演练和仓库外调用方确认已转换为强制门禁、验证脚本和签字清单，仍需在对应环境执行。
- P2：4/4 已实施，包括轻量轮询工具、Task 生命周期执行器、Mock 生成器目录迁移和报告版本口径修正。
- 出生日期：已改为后端生成身份证号的权威输入，不再是仅展示字段。

## 三、出生日期语义修正

### 请求与校验

前端继续提交：

```json
{
  "currentDate": "2026-07-15",
  "birthDate": "1986-07-14",
  "age": 40
}
```

后端 `ApplicationDataSubmission` 要求 `birthDate` 必填，并校验：

- 出生日期不得晚于当前日期；
- 按周岁计算的年龄必须等于提交的 age；
- 不一致时返回 HTTP 400，不再静默忽略。

### 证件号生成

身份证号结构现在直接使用请求中的 birthDate：

```text
6 位地区码 + YYYYMMDD(birthDate) + 3 位顺序码 + 校验码
```

自动化测试明确验证证件号第 7–14 位等于提交的 `19860714`。由于单次最大生成数量已降到 1,000，测试也验证同一出生日期、同一性别下最大请求规模内证件号保持唯一。

### tellerNo

`tellerNo` 继续作为真实业务输入，进入每条生成记录，并显示在页面表格、复制文本和 CSV 中。

## 四、P0 实施结果

### P0-1：非幂等写任务取消状态错误

已完成：

- 运行中的非幂等写 Job 拒绝取消并返回 409；
- pending/retrying 阶段仍允许取消；
- 外部调用期间取消的交错测试验证最终状态保持 success；
- 非幂等写任务仍禁止通用 retry 和 Broker 自动重放。

### P0-2：卡转账目标卡未执行

已完成：

- targetCard 贯穿 Schema、Job payload、Service、Adapter 和 Mock Store；
- 同一事务锁定源卡和目标卡；
- 源卡扣款、目标卡入账；
- 覆盖目标卡不存在、同卡转账和余额不足。

### P0-3：100,000 条完整 Job JSON

已完成：

- 后端硬上限改为 1,000；
- 前端上限来自后端配置；
- 默认 2 MiB 结果大小保护；
- 超限立即失败，不把超限结果写入 Job.result；
- 覆盖 1,001 条拒绝和结果大小超限测试。

### P0-4：Mock 状态不能跨 Worker

已完成：

- 新增 `MockToolState` 数据表和 `0004_mocktoolstate.py`；
- 卡/贷款状态由进程内字典迁移到数据库；
- 查询和 mutation 使用事务及行锁；
- 独立 Store 实例共享同一状态。

## 五、P1 实施结果

### P1-1：申请链接真实协议闭环

本地实现：

- 保留一次调用、五字段表单和 `REQ_MESSAGE == biz_content`；
- 新增 `APPLICATION_LINK_PROTOCOL_CONFIRMED`，默认 false；
- 真实模式在协议未确认时直接拒绝调用；
- 真实模式不再接受静态 sign，必须配置 `APPLICATION_LINK_SIGNER` 可调用路径；
- signer 必须根据完整 message 返回非空字符串；
- Mock 模式仍允许静态 sign，便于协议测试。

需要真实环境完成：签名实现、timestamp、路径、成功码和响应字段联调。完成后才能设置 `APPLICATION_LINK_PROTOCOL_CONFIRMED=true`。

### P1-2：申请链接异常错误归类

已完成。产品、环境和合作项目错误保留各自业务含义；无效合作项目不会再误报产品不存在。

### P1-3：新增页面无限轮询

已完成：

- 申请数据、卡状态、贷款状态和核实审批统一使用轻量 `jobPolling.ts`；
- 默认截止时间 150 秒；
- 支持 AbortSignal；
- Hook 卸载和新流程开始时取消旧轮询；
- 取消不误报业务失败。

### P1-4：birthDate / tellerNo 静默忽略

已完成。birthDate 用于证件号且校验年龄；tellerNo 进入结果和导出，详见第三节。

### P1-5：申请数据配置重复

已完成。环境、性别、主体类型和 maxCount 由后端配置接口下发；前端只保留默认值。

### P1-6：公开查询参数读取 payload

已完成：

- `includePayload=true` 不再生效；
- 普通详情、重试和取消响应均不返回 payload；
- 新增独立 `GET /api/jobs/{id}/payload`；
- 仅已认证且 `is_staff=true` 的用户可访问；
- 未认证或普通用户返回 403。

### P1-7：真实异步边界验证

本地自动化已覆盖：

- 外部调用期间取消；
- 转账完整账务行为；
- 大结果限制；
- 跨 Store 实例共享状态；
- 页面轮询取消；
- Task 自动发现和注册。

新增 `Alkaid-python/scripts/verify_celery_runtime.py`。在真实 RabbitMQ/Worker 环境执行：

```bash
cd Alkaid-python
python scripts/verify_celery_runtime.py --min-workers 2
```

脚本检查 Worker 可达性和每个 Worker 的 7 个产品数据 Task 注册。Worker 强杀及外系统成功后进程退出仍必须在隔离集成环境执行，不能在本地无 Broker 环境伪造结果。

### P1-8：仓库外核实审批调用方

新增 `docs/compatibility/verification-approval-async-migration.md`，包含：

- 同步响应到 Job 响应的迁移示例；
- 脚本、Postman/Apifox、页面和服务调用方签字项；
- 终态、超时和取消处理要求；
- Celery 环境验证命令。

仓库内调用方已完成；仓库外项目仍必须由发布负责人按清单签字。

## 六、P2 实施结果

### P2-1：轻量 Job 轮询工具

已完成。新增 `Alkaid-react/src/utils/jobPolling.ts`，只抽取截止时间、取消、等待和终态判断，不引入通用 Workflow 框架。

### P2-2：Celery Task 生命周期重复

已完成。新增 `Alkaid-python/apps/jobs/task_runner.py`：

- 统一 running、deadline、取消检查、success/failed/timed_out；
- 统一异常落 Job；
- 业务 Task 继续显式定义校验、operation、进度节点和 Service 调用；
- 7 个产品数据 Task 均接入共享执行器。

### P2-3：生成器目录职责漂移

已完成。生成器从 `apps/integrations/application_data` 迁移到独立的 `apps/mock_data/application_generator.py`。Integration 与 Product Data 均只依赖中立 Mock 算法目录，架构检查继续通过。

### P2-4：报告版本状态过期

已完成。本报告固定记录：

- 被审查业务版本；
- 原报告提交版本；
- 本次整改实施代码提交；
- 本报告文档提交。

## 七、数据库与配置

### Migration

```text
apps/jobs/migrations/0004_mocktoolstate.py
```

部署时必须执行 Django migrate。

### 新增配置

```text
APPLICATION_DATA_MAX_RESULT_BYTES=2097152
APPLICATION_LINK_PROTOCOL_CONFIRMED=false
APPLICATION_LINK_SIGNER=
```

真实申请链接环境必须同时完成协议确认并配置 signer。

## 八、验证结果

| 验证项 | 结果 |
| --- | --- |
| 后端完整 pytest | `54 passed` |
| Python Ruff | 通过 |
| 架构依赖检查 | 通过 |
| 前端 Vitest | `7 files / 14 tests passed` |
| TypeScript + Vite build | 通过 |
| git diff --check | 通过 |

前端仍有单 bundle 超过 500 kB 的既有告警，不影响构建成功。

## 九、仍需外部执行的发布门禁

以下不是缺失代码，而是只能在真实环境完成的验证：

1. 提供并配置真实 `APPLICATION_LINK_SIGNER`；
2. 完成申请链接 timestamp、路径、成功码和响应字段联调；
3. 完成核实审批 refresh 真实协议联调；
4. 运行至少双 Worker 的 `verify_celery_runtime.py`；
5. 执行 Worker 强杀和外系统成功后进程退出演练；
6. 完成仓库外核实审批调用方签字清单。

任何一项未完成时，不应把对应真实模式标记为已上线。

## 十、最终判定

- 本地 P0/P1/P2 代码整改：**完成**。
- 出生日期证件号语义：**完成并有自动化覆盖**。
- Mock/测试环境：**可进入合并复核**。
- 真实外系统生产模式：**受第九节门禁约束，门禁完成后方可上线**。
