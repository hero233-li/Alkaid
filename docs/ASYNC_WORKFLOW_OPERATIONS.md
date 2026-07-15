# 异步工作流实施与运维说明

本文档记录合并到 `main` 的异步 Job、外系统 Integration、环境变量、数据库迁移和验证方式。
具体请求及响应字段以 [`API.md`](./API.md) 为准。

## 1. 调用链

所有异步业务遵循同一边界：

```text
React Page / Hook
  → Django View（Schema 校验、创建 Job、投递 Celery）
  → Celery Task（TaskRunner 管理状态、超时、取消）
  → Product Service（业务步骤）
  → Integration Adapter（外系统协议）
  → HttpClient / Mock Store
  → Job.result、JobLog、JobApiCall
  → GET /api/jobs/{id} 或 SSE 返回前端
```

目录职责：

- `apps/product_data/<feature>/`：Schema、View、Task 和业务 Service；不拼接真实外系统报文。
- `apps/integrations/<system>/`：请求/响应模型、Adapter、Mock transport 和真实 HTTP 协议。
- `apps/jobs/`：Job 状态、幂等、重试、取消、超时、审计、SSE 和共享 TaskRunner。
- `Alkaid-react/src/utils/jobPolling.ts`：150 秒前端轮询截止、AbortSignal 和终态处理。

申请链接保持一次外部调用：

```text
View → Job → Task → Service → Adapter
  → msg_id + sign + timestamp + REQ_MESSAGE + biz_content
```

`REQ_MESSAGE` 与 `biz_content` 使用同一份序列化业务报文。真实模式必须先完成协议确认并配置
Signer。卡和贷款 Mock 状态存入 MySQL，Key 包含环境，支持多个 Worker 共享且避免环境串用。

## 2. 环境变量

模板分别位于：

- 本地总入口：`.env.local.example`
- 后端开发：`Alkaid-python/.env.example`
- 后端服务器：`Alkaid-python/.env.server.example`

关键变量：

| 分组 | 变量 | 说明 |
| --- | --- | --- |
| 运行模式 | `EXTERNAL_SYSTEM_MODE` | `mock` 或 `real`；服务器配置强制为 `real` |
| Django | `DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS` | 服务器必须使用独立密钥和明确域名 |
| MySQL | `MYSQL_HOST/PORT/DATABASE/USER/PASSWORD` | 开发、验证、生产必须使用不同数据库 |
| Celery | `CELERY_BROKER_URL`、`CELERY_QUEUE`、`CELERY_TASK_ALWAYS_EAGER` | 生产禁止 eager；Broker 凭据不得提交 Git |
| Job | `JOB_RETENTION_HOURS`、`JOB_LOG_RETENTION_HOURS`、`JOB_MAX_HTTP_BODY_BYTES` | 生命周期和审计大小限制 |
| 超时 | `*_TIMEOUT_SECONDS` | 各业务 Job 的后端执行截止时间 |
| 申请数据 | `APPLICATION_DATA_MAX_RESULT_BYTES` | 默认 2 MiB；单次条数硬上限为 1,000 |
| 申请链接 | `APPLICATION_LINK_BASE_URL`、`APPLICATION_LINK_API_TOKEN` | 真实接口地址和 Token |
| 申请链接门禁 | `APPLICATION_LINK_PROTOCOL_CONFIRMED`、`APPLICATION_LINK_SIGNER` | 真实模式 readiness 必查 |
| 其他外系统 | `MOCK_PRODUCT_BASE_URL`、`BUSINESS_ACCESS_*`、`VERIFICATION_APPROVAL_*` | 真实模式必须配置 |

示例文件只允许占位值。真实密码、Token、Signer 密钥和账号只通过部署环境注入，不写入仓库、
Job payload、结果或审计日志。`VERIFICATION_APPROVAL_DEBUG_DELAY_SECONDS` 默认必须为 `0`。

## 3. 数据库变更

Jobs App 的迁移链完整顺序为：

```text
0001_initial
→ 0002_job_execution_config
→ 0003_job_status_deadline_index
→ 0004_mocktoolstate
```

- `0003` 为 `Job(status, deadline_at)` 增加超时收敛索引。
- `0004` 新增 `MockToolState(namespace, key, payload, updated_at)`，并对
  `(namespace, key)` 建立唯一约束，用于多 Worker 共享卡/贷款 Mock 状态。
- 已移除的 `workflows` App 不会自动 DROP 历史表。需要清理时由 DBA 在备份后单独执行，发布
  Migration 不做破坏性删除。

部署顺序：

```bash
cd Alkaid-python
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py migrate
```

生产执行前必须备份数据库；开发、候选验证和生产分别使用 `alkaid_dev`、`alkaid_verify`、
`alkaid_prod`，禁止候选代码直接连接生产库。

## 4. 接口与状态约束

- 创建类接口返回 `202 + Job`，相同幂等键和相同请求返回原 Job。
- 普通 Job 查询、重试和取消响应不返回原始 payload；仅 staff 可访问
  `GET /api/jobs/{id}/payload`。
- 非幂等写 Job 进入 `running` 后拒绝取消和通用重试，避免外系统成功而本地误报取消。
- 申请数据的 `birthDate` 是身份证号生日段的权威输入，并与 `age/currentDate` 校验。
- 卡转账要求目标卡存在于同一环境，源卡扣款和目标卡入账在同一事务中完成。
- `/health/ready/` 不调用真实业务接口；RabbitMQ 和 Worker 使用独立脚本验证。

## 5. 测试方式

后端完整验证：

```bash
cd Alkaid-python
../.venv/bin/python -m pytest
../.venv/bin/python -m ruff check .
../.venv/bin/python scripts/check_architecture.py
../.venv/bin/python manage.py makemigrations --check --dry-run
```

前端完整验证：

```bash
cd Alkaid-react
npm test -- --run
npm run build
```

真实 RabbitMQ 和至少双 Worker 的验证：

```bash
cd Alkaid-python
../.venv/bin/python scripts/verify_celery_runtime.py --min-workers 2
```

发布前还必须在隔离环境执行 Worker 强杀、外系统成功后进程退出演练，并完成核实审批仓库外
调用方确认。真实申请链接只有在协议、时间戳、路径、成功码、响应字段和 Signer 全部联调完成后，
才允许设置 `APPLICATION_LINK_PROTOCOL_CONFIRMED=true`。

## 6. 合并前审计口径

审计范围使用 `git diff main...<feature-branch>`，并至少检查：

```bash
git diff --check main...HEAD
git diff --name-status main...HEAD
rg -n "print\\(|breakpoint\\(|debugger;|console\\.(log|debug)\\(" Alkaid-python Alkaid-react/src
```

CLI 脚本的进度输出以及 Workbench 生成示例中的 `print/console.log` 属于产品功能，不视为临时调试。
测试中的 `test`、`secret-token` 仅为隔离测试值，不得替换为真实凭据。
