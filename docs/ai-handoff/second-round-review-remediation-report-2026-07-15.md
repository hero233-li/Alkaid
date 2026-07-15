# 第二轮审查整改实施报告（2026-07-15）

## 一、版本与结论

- 第二轮审查基线：`6976a0a`
- 第二轮整改实施代码提交：`00fa799`
- 本报告文档提交：本文件所在提交
- 当前分支：`agent/job-and-application-link-refactor`
- 上轮 P0：复核保持完成，本轮未发现新 P0。
- 本轮 P1：1–6 已完成代码整改；P1-7 继续保留为真实协议确认门禁。
- 本轮 P2：TaskRunner 保持不变；`acks_late` 风险分级、Mock 状态独立领域及清理策略继续作为后续优化；贷款全命名空间扫描已随本轮环境隔离一并消除。

## 二、P1 实施结果

### 1. in-flight Abort 识别

- `jobPolling.ts` 在 `fetchJob()` 异常处再次检查 `signal.aborted`，即使 Axios 包装了异常也会统一抛出 `AbortError`。
- Axios 响应拦截器保留 `CanceledError/ERR_CANCELED`，不再转换成普通 `Error`。
- 新增“HTTP 请求已发出后 abort”的自动化测试。

### 2. 旧流程 finally 清除新 Activity

- 申请数据、卡状态、贷款状态均使用 Controller 所有权清理。
- 只有 `controllerRef.current === controller` 的当前流程可以清空 Activity。
- 新增流程 A 被流程 B 取消后，A 的 finally 不清除 B Activity 的 Hook 测试。

### 3. Mock 状态环境隔离

状态 Key 调整为：

```text
card_status: <environment>:<cardNo>
loan_status: <environment>:<customerNo>
```

卡和贷款操作同时校验环境、客户与持久化状态。相同客户在不同环境查询、操作时不再共享余额、冻结状态或贷款状态。

### 4. 首次创建竞争

- 首次状态建立统一使用 ORM `get_or_create`，依靠数据库唯一约束处理并发创建竞争。
- 对 SQLite/MySQL 的短暂锁冲突执行有限次数退避重试。
- 新增双线程同时首次查询测试，验证最终只有一条 `MockToolState`。

### 5. 真实申请链接 readiness

真实模式下 `/health/ready/` 现在检查：

- `APPLICATION_LINK_PROTOCOL_CONFIRMED=true`；
- `APPLICATION_LINK_SIGNER` 已配置；
- Signer 可成功加载且可调用。

任一项不满足时返回 HTTP 503。RabbitMQ/Worker 仍由独立运行时验证脚本检查，readiness 不发起真实外系统请求。

### 6. 申请数据配置加载失败

- Hook 新增 `configError`；
- 页面展示明确错误，不再永久显示 Spin；
- 提供“重新加载”操作。

### 7. 核实审批 refresh 语义

保持发布门禁：真实协议确认前不把 `verification_approval.refresh` 加入非重试/运行中不可取消集合。若联调确认存在写副作用，再按非幂等写任务策略收敛。

## 三、P2 处理结果

- TaskRunner：保持当前克制抽象，不继续扩大。
- `acks_late=False`：本轮不拆 Task；待按纯查询、本地生成、非幂等写操作完成风险分级后调整。
- 贷款扫描：已改为按 `environment + customerNo` 精确锁定一条状态，不再锁定并扫描整个命名空间。
- MockToolState 领域与清理：本轮不迁 App；后续数据量增长时再增加过期和重置策略。
- 上轮报告状态：已修正为“已提交并推送至当前远端分支”。

## 四、验证结果

| 验证项 | 结果 |
| --- | --- |
| 后端 pytest | `57 passed` |
| Python Ruff | 通过 |
| 架构依赖检查 | 通过 |
| 前端 Vitest | `9 files / 16 tests passed` |
| TypeScript + Vite build | 通过 |
| 并发首次创建 | 双线程收敛为一条状态 |

前端构建仍有单 bundle 超过 500 kB 的既有告警，不影响构建成功。

## 五、最终判定

- Mock/测试环境：可进入合并复核。
- 本轮优先 P1 并发问题：已整改并有自动化覆盖。
- 真实外系统：仍受协议、Signer、双 Worker、强杀演练及仓库外调用方确认门禁约束，不能仅凭本地测试标记上线。
