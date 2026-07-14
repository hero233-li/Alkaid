# 最终实施审查报告

## P0：合并前必须处理

### 1. 新核实审批 Celery Task 没有加入自动发现入口

真实 Worker 可能收到 `unregistered task`。

`config/celery.py` 使用 Celery 自动发现，但 `apps/product_data/tasks.py` 目前只导入产品申请、申请链接和业务准入 Task，没有导入新增的 `execute_verification_approval_task`。Web 侧 dispatcher 虽然能够发送该任务，但独立 Worker 不应依赖 Web 进程运行时的动态导入。当前测试全部使用 `CELERY_TASK_ALWAYS_EAGER=True`，因此不会暴露真实 Worker 注册问题。

合并前至少补：

```python
from apps.product_data.verification_approval.tasks import (
    execute_verification_approval_task,
)
```

并加入 `__all__`，再进行一次非 Eager Worker 注册验证。

### 2. 前端仍直接调用 `crypto.randomUUID()`

这会复现已经出现过的内网页面运行错误。

新核实审批异步请求直接调用 `crypto.randomUUID()`；申请链接、业务准入和产品申请也仍采用相同实现，没有兼容兜底。

此前的局域网 HTTP 页面已经实际出现过：

```text
crypto.randomUUID is not a function
```

应统一使用带降级逻辑的请求 ID 方法，不要在四个页面分别直接调用 `crypto.randomUUID()`。

### 3. 异步外系统写操作仍没有解决重复执行

核实审批异步化进一步扩大了风险。

申请链接 Task 使用 `acks_late=True` 和 `reject_on_worker_lost=True`，一次任务又连续执行“创建申请”和“生成链接”两次外部调用。

新核实审批 Task 同样开启 Worker 丢失重投，但领取、退回、核实项更新和快捷操作都是外部写操作。

Adapter 当前只传递 Trace ID 和审计 Observer，没有向外系统传递稳定幂等键；通用 Job 接口又允许失败、超时和取消任务重新执行。

可能出现：

```text
外系统写成功
→ Worker 在本地保存成功状态前退出
→ RabbitMQ 重投或用户重试
→ 同一个领取、提交、创建申请再次执行
```

合并到真实模式前必须明确一种策略：

- 外系统支持幂等：传递按 `workflow_id + operation/step` 派生的稳定幂等键；
- 外系统不支持幂等：禁止非幂等写操作自动重放和通用 Job 重试；
- 申请链接第一步成功后的恢复，还需避免重新创建申请。

---

## P1：建议处理

### 1. 核实审批响应协议发生破坏性变化，API 文档没有同步

核实审批保留了旧 URL 和请求 Body，但原接口现在统一返回 HTTP `202 + Job`，不再同步返回核实任务。

当前前端已完成适配，但 `docs/API.md` 仍把核实审批描述为直接返回任务上下文，也没有新增的刷新接口；接口总览同样缺少申请链接配置接口。

应更新 API 文档，并确认没有仓库外脚本或旧前端依赖同步响应。存在外部调用方时，这项应提升为 P0。

### 2. 刷新接口仍建立在未确认的真实外系统协议上

报告明确说明 `/verification/tasks/{taskId}/refresh` 的路径、请求字段和返回 Schema 尚未经过真实接口确认。

当前代码已经硬编码该路径，并将刷新标记为 `RetryMode.SAFE`；前端在核实项更新后会自动调用刷新。

建议真实联调前确认：

- 路径；
- Context 是否需要完整回传；
- 返回模型；
- 刷新是否确实无副作用、允许自动重试。

### 3. 测试没有覆盖异步化最危险的失败链

当前核实审批测试覆盖了查询、领取、核实项更新、刷新、完成、提交和退回，但主要都是 Eager Mock 成功流程。

缺少：

- 独立 Worker Task 注册；
- Broker 可连接但 Worker 未注册任务；
- 外系统 HTTP 失败和业务码失败；
- Worker 丢失与任务重投；
- 写操作重复执行；
- Job 手动重试；
- 超时和执行中取消；
- `JobApiCall` 对每种 mutation 的失败审计；
- `supplement`、`approval-submit` 和核实项取消路径。

申请链接协议测试目前主要验证 `/applications`，没有分别验证太阳码和动态链接生成接口的真实 URL、请求 Body 和响应映射。

### 4. 前端只有 TypeScript/Vite 构建，没有运行时行为测试

至少应覆盖：

- 后端配置转换为申请链接级联选项；
- 稳定产品代码和环境代码提交；
- Job 成功、失败、超时后的轮询终止；
- 核实项成功后自动刷新；
- 原操作成功、自动刷新失败时保留原操作结果；
- 无 `crypto.randomUUID()` 环境下仍能提交。

### 5. Job 轮询仍返回完整 payload

新异步核实审批会把完整任务 Context 暴露在每次 Job 查询中。

核实审批创建 Job 时把完整 Context 放入 payload，而通用 `serialize_job()` 会直接返回原始 `job.payload`。

当前页面轮询只需要：

```text
id
status
stage
progress
result
errorMessage
```

真实客户数据上线前，建议普通轮询默认不返回 payload，原始参数只通过受权限控制的详情接口查看。

### 6. 新核实审批轮询没有 AbortSignal 或客户端截止时间

当前使用无限 `while (true)`，页面离开、组件卸载或 Job 长时间无法进入终态时，没有主动停止机制。

建议至少增加客户端截止时间和卸载取消，不需要为此重构整个 Job 框架。

---

## P2：以后优化

### 1. 三个前端异步模块已经出现明显重复

申请链接、业务准入和核实审批分别维护：

```text
workflowRequestConfig
submit Job
get Job
while(true) 轮询
终态判断
activity 状态转换
```

后续功能继续增加时，再抽一个轻量 Job Client/Hook；本次不要继续扩大重构范围。

### 2. 核实审批 Service 中的 Context 校验已经退化为恒真检查

Service 调用：

```python
_validate_context(context.id, context)
```

两个参数来自同一个对象，因此无法再验证原 URL 中的 `task_id`。真正的路径校验已经在 View 完成。

后续可以删除这层重复校验；若确实需要 Task 再校验，则应把独立 `task_id` 持久化进 Job payload。

### 3. Backend Task 模板存在重复，但当前不建议抽 BaseTask

产品申请、申请链接、业务准入和核实审批都包含：

```text
mark_running
deadline
progress
cancel
execute
mark_success/failed
```

当前每个 Task 仍较短，业务行为也没有完全稳定。暂时保留显式实现，避免重新引入通用 Workflow/Handler 层。

### 4. 最终报告中的 GitHub 状态已经过期

报告仍写“尚未提交、尚未推送”，但审查方指出当前提交已经位于远端分支。

合并前更新报告状态即可，不影响运行。

---

## 整改处置记录（2026-07-14）

### P0-1：接受，已实施

- 已在 `apps/product_data/tasks.py` 导入并导出核实审批 Task。
- 已增加非 Eager 的 Celery 默认模块加载/任务注册测试。
- 该测试验证独立 Worker 所依赖的自动发现入口；尚未在本机启动真实 RabbitMQ Worker 做端到端消费验证。

### P0-2：接受，已实施

- 新增共享 `createRequestId()` / `createWorkflowHeaders()`。
- 四个需求范围内的前端模块均已移除直接 `crypto.randomUUID()` 调用。
- 优先使用原生 `randomUUID`，不可用时降级到 `getRandomValues`，再降级到时间戳与伪随机数。
- 已增加无 `randomUUID` 环境的运行时测试。

### P0-3：部分接受，已实施保守策略

- 真实外系统尚未确认幂等 Header，因此未虚构或擅自发送幂等键。
- 四个外系统 Task 已关闭 `acks_late` 和 `reject_on_worker_lost`，Worker 丢失时不由 Broker 自动重投。
- 产品申请、申请链接、业务准入写操作，以及核实审批 claim/return/item-update/action，均禁止通过通用 Job retry 再次执行。
- 查询以及刷新仍允许用户显式重新发起；刷新外部 Endpoint 已取消 `RetryMode.SAFE`，协议确认前不做自动 HTTP 重试。
- 取舍：可避免不受控重复写；若外系统已经成功而 Worker 尚未写入本地成功状态便退出，Job 需要人工核对，不能自动恢复。申请链接两阶段调用仍需要真实外系统幂等/查询协议才能实现安全续跑。

### P1-1：接受，已实施

- `docs/API.md` 已补充申请链接配置接口、核实审批 `202 + Job` 响应、刷新接口、轮询 payload 策略和重试限制。
- 仓库外调用方是否依赖旧同步响应仍无法通过当前代码仓库确认。

### P1-2：部分接受，已实施可确认部分

- 刷新继续完整回传后端上次返回的 context。
- 未确认真实协议前，已取消外部刷新请求的自动 HTTP 重试。
- 路径、请求字段、返回 Schema 和无副作用属性仍需真实接口文档或联调确认。

### P1-3：部分接受，已补主要自动化覆盖

- 已补 Celery 自动发现注册、HTTP 失败、业务码失败、mutation 失败审计、非幂等 Job retry 拒绝、Task 不重投、轮询 payload、太阳码/动态链接 URL/Body/映射测试。
- 已覆盖 supplement、approval-submit 和核实项取消成功链。
- 真实 Broker 可连接但 Worker 未注册、Worker 进程强杀、外系统成功后 Worker 丢失等场景需要 RabbitMQ 集成环境，当前本地测试不能完全模拟。

### P1-4：接受，已实施

- 新增 Vitest + Testing Library 运行时测试。
- 覆盖申请链接配置级联和稳定代码提交、Job 成功/失败/超时/取消、核实项后自动刷新、自动刷新失败时保留原操作结果，以及无 `crypto.randomUUID()` 降级。

### P1-5：部分接受，已实施轮询最小化

- 普通 `GET /api/jobs/{id}` 默认不返回 payload。
- 仅显式 `includePayload=true` 时返回；产品申请现有兼容调用已显式请求。
- 尚未新增独立的、额外权限控制的原始参数详情接口。

### P1-6：接受，已实施

- 核实审批轮询增加 150 秒默认客户端截止时间和 `AbortSignal`。
- Hook 卸载时主动取消当前轮询，并避免把取消误报为业务失败。

### P2-1：拒绝本次实施

- 遵循审查意见，本次不抽取共享 Job Client/Hook，避免扩大范围。

### P2-2：接受，已实施

- 已删除 Service 中参数同源的恒真 Context 校验；URL 与 context 的一致性仍由 View 校验。

### P2-3：接受建议，不改代码

- 保留四个显式 Task，不抽 BaseTask。

### P2-4：接受，已更新报告

- 远端分支基线提交已存在；本轮审查整改仍是本地未提交差异。最终报告分别说明基线与本轮差异状态。
