# Alkaid HTTP API

本文档描述 `main` 分支中 Django 后端（`Alkaid-python`）当前暴露的 HTTP 接口。它不把
`/admin/` 或前端静态资源路由当作对外 API。

## 1. 使用约定

- 本地开发的服务根地址通常为 `http://127.0.0.1:8000`；以下路径均相对该地址。
- 所有 JSON 请求都应发送 `Content-Type: application/json`。
- 产品与 Job 的 REST 接口不带末尾 `/`。请使用下文列出的精确路径。
- 目前这些业务接口没有应用层的身份校验；部署时应在反向代理或网关处补充认证、授权、限流和 TLS。
- 产品申请、申请链接生成、任务重试和任务取消已豁免 CSRF。

### 1.1 常规响应信封

产品申请和 Job 接口使用统一响应格式：

```json
{
  "ok": true,
  "message": "",
  "data": {}
}
```

失败时 `ok` 为 `false`，`message` 包含可读错误信息，`data` 通常为 `null`。`405 Method Not Allowed` 由 Django 的方法装饰器生成，不保证采用上述格式。

### 1.2 接口总览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health/` | 健康检查 |
| `GET` | `/health/ready/` | 数据库与静态运行配置就绪检查 |
| `GET` | `/api/product-data/applications/config` | 获取产品申请表单配置 |
| `POST` | `/api/product-data/applications` | 创建或幂等返回产品申请 Job |
| `POST` | `/api/product-data/tools/application-links/generate` | 创建申请链接生成 Job |
| `GET` | `/api/product-data/business-access/config` | 获取业务准入环境配置 |
| `POST` | `/api/product-data/business-access/search` | 创建业务准入查询 Job |
| `POST` | `/api/product-data/business-access/{recordId}/invalidate` | 创建准入记录失效 Job |
| `POST` | `/api/product-data/business-access/{recordId}/notifications/query` | 创建通知查询 Job |
| `POST` | `/api/product-data/business-access/{recordId}/notifications/{notificationId}/{push-new\|push-old}` | 创建通知推送 Job |
| `GET` | `/api/product-data/verification-approval/config` | 获取核实审批搜索配置 |
| `POST` | `/api/product-data/verification-approval/search` | 查询核实审批任务 |
| `POST` | `/api/product-data/verification-approval/{taskId}/claim` | 领取核实任务 |
| `POST` | `/api/product-data/verification-approval/{taskId}/return` | 退回核实任务 |
| `POST` | `/api/product-data/verification-approval/{taskId}/items/{itemId}` | 更新核实项 |
| `POST` | `/api/product-data/verification-approval/{taskId}/actions/{action}` | 执行核实审批快捷操作 |
| `GET` | `/api/jobs/{jobId}` | 查询 Job 详情和已保存日志 |
| `POST` | `/api/jobs/{jobId}/retry` | 重试失败、超时或已取消 Job |
| `POST` | `/api/jobs/{jobId}/cancel` | 请求取消 Job |
| `GET` | `/api/jobs/{jobId}/logs` | 增量查询 Job 日志 |
| `GET` | `/api/jobs/{jobId}/logs/stream` | 订阅 Job 日志与状态（SSE） |
| `GET` | `/api/jobs/{jobId}/calls/{callId}` | 查询一次外部接口调用审计记录 |

## 2. 健康检查

### `GET /health/`

服务存活时返回 HTTP `200`：

```json
{"status":"ok"}
```

该接口只表示 Web 进程存活，不检查数据库、Celery 或外部系统连通性，只接受 `GET`。

### `GET /health/ready/`

检查数据库查询、产品 Catalog、产品外系统接口覆盖和全部原始报文结构。全部正常返回 `200` 和
`{"status":"ready","checks":...}`；任一项失败返回 `503`。该接口不主动调用真实外系统，
因此不会产生业务副作用；Worker/Broker 可用性仍由进程监管和运行监控负责。

## 3. 产品申请

产品申请为异步操作：创建接口只创建 Job 并投递 Celery 任务。随后通过 [Job 接口](#5-job-接口)查询、轮询或订阅执行进度。

### 3.1 读取页面配置

#### `GET /api/product-data/applications/config`

返回动态表单配置，客户端应以该响应为环境、产品、地区、机构、网点和页面字段的来源，而不是硬编码选项。

`data` 的主要结构如下：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | string | 配置标识 |
| `version` | integer | 页面配置版本 |
| `environments` | `{label, value}[]` | 可选环境 |
| `products` | object[] | 产品、可用环境、地区/机构/网点层级、字段组与必填字段 |
| `fieldSets` | `Record<string, string[]>` | 字段组到字段名的映射 |
| `fields` | object[] | 字段展示与校验元数据，例如 `name`、`control`、`required`、`submit`、`options` |
| `cascadeResetMap` | `Record<string, string[]>` | 上游选择变更时要清空的下游字段 |

当前 `products[].value` 为 `product-a`、`product-b`、`product-c`。配置错误时返回 `500` 和常规错误信封。

### 3.2 创建产品申请

#### `POST /api/product-data/applications`

可选请求头：

| 请求头 | 作用 |
| --- | --- |
| `X-Idempotency-Key` | 幂等键。使用同一键和相同业务请求会返回原 Job，不会再次投递；建议为长度不超过 128 的 UUID。 |
| `X-Trace-ID` | 调用链标识，会写入 Job 和外部调用审计。未提供时服务端生成。 |

请求体：

```json
{
  "name": "产品A-产品申请",
  "product": "product-a",
  "payload": {
    "environment": "env-1",
    "product": "product-a",
    "location": "广东省广州市",
    "branch": "广东省机构",
    "outlet": "广东省网点",
    "personName": "测试用户",
    "certificateNo": "330101199001011234",
    "cardNo": "6222000000000000",
    "phone": "13800138000",
    "customerType": "farmer",
    "whitelistEnabled": true,
    "redShieldEnabled": true
  }
}
```

字段规则：

- `name` 为 1–255 个字符，`product` 为 1–128 个字符；`payload` 必须是对象。
- `environment` 必须是该产品支持的环境；`location`、`branch`、`outlet` 必须构成配置中存在的层级。
- `payload.product` 可以省略；如果发送，必须等于顶层 `product`。
- `customerType` 必须是 `farmer`、`legal_person` 或 `shareholder`。法人和股东必须提供非空的 `companyName`；农户不能提供非空 `companyName`。旧字段 `legalPerson` 不可提交。
- `payload` 不允许包含当前产品、字段组和申请方式之外的未知字段。`companyName` 与 `creditCode` 是当前企业字段组中的可选字段。

当前执行配置（目录版本为 5）还要求以下产品/申请方式字段。未提供 `applicationMethod` 时使用 `normal`，服务端会把最终选中的方式写回 Job 的 `payload.applicationMethod`。

| 产品 | `applicationMethod` | 除通用字段外的必填字段 |
| --- | --- | --- |
| `product-a` | `normal` | `cardNo`、`whitelistEnabled`、`redShieldEnabled` |
| `product-a` | `dynamic` | `cardNo`、`whitelistEnabled`、`redShieldEnabled`、`dynamicTerm`、`dynamicAmount` |
| `product-a` | `extra` | `cardNo`、`whitelistEnabled`、`redShieldEnabled`、`extraReason` |
| `product-b` | `normal` | `redShieldEnabled` |
| `product-b` | `dynamic` | `redShieldEnabled`、`dynamicTerm`、`dynamicAmount` |
| `product-c` | `normal` | `creditEnabled` |
| `product-c` | `dynamic` | `creditEnabled`、`dynamicTerm`、`dynamicAmount` |

通用必填字段为 `environment`、`location`、`branch`、`outlet`、`personName`、`certificateNo`、`phone` 和 `customerType`。产品页面配置或执行配置升级后，应重新读取配置并以实际部署的配置为准。

首次成功创建返回 HTTP `202`；同幂等键、相同请求返回 HTTP `200` 和原 Job。参数校验失败返回 `400`；幂等键已被不同请求占用时返回 `409`。

成功响应的 `data` 是 [Job 对象](#41-job-对象)。

## 4. Job 状态与对象

产品申请创建后，其状态依次可能为：

```text
pending / retrying → running → success | failed | cancelled | timed_out
                           └→ cancel_requested → cancelled
```

`success`、`failed`、`cancelled`、`timed_out` 为终态。`cancel_requested` 表示运行中的 worker 已收到取消意图，实际结束由 worker 处理。

### 4.1 Job 对象

除外部调用明细外，创建、详情、重试、取消接口都返回下列对象：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | Job ID |
| `name` / `product` | string | 创建时提交的名称和产品 |
| `workflowId` | UUID string | Job 的工作流标识 |
| `status` | string | Job 状态 |
| `stage` | string | 当前执行阶段，例如 `created`、`validate`、`execute`、`completed` |
| `progress` | integer | 进度，范围 0–100 |
| `payload` / `result` | object | 原始提交内容（含服务端补充的申请方式）和执行结果 |
| `executionConfigVersion` | integer | 创建该 Job 时冻结的产品执行配置版本 |
| `errorMessage` | string or null | 失败或超时原因 |
| `traceId` / `idempotencyKey` | string | 调用链与幂等标识 |
| `attemptCount` | integer | 当前执行次数 |
| `timeoutSeconds` | integer | 单次任务超时秒数 |
| `deadlineAt` / `createdAt` | ISO 8601 datetime | 截止时间和创建时间 |
| `logs` | JobLog[] | 已保存日志；仅该完整 Job 对象包含 |

`logs` 中每项为：

```json
{
  "id": 12,
  "jobId": 7,
  "level": "INFO",
  "step": "validate",
  "message": "产品申请参数校验完成",
  "metadata": {},
  "createdAt": "2026-07-10T12:00:00+08:00"
}
```

## 5. Job 接口

### `GET /api/jobs/{jobId}`

返回 Job 详情和所有当前保留的日志。Job 不存在时返回 `404`。

### `POST /api/jobs/{jobId}/retry`

只允许重试状态为 `failed`、`timed_out` 或 `cancelled` 的 Job。成功后 Job 状态变为 `retrying`、进度归零、执行次数加一，并重新投递任务。状态不允许重试时返回 `409`；Job 不存在时返回 `404`。

### `POST /api/jobs/{jobId}/cancel`

- `pending` 或 `retrying` 的 Job 会立即变为 `cancelled`；
- `running` 的 Job 会变为 `cancel_requested`，worker 在安全检查点结束它；
- 已终态的 Job 保持原状态，并仍返回 `200`。

Job 不存在时返回 `404`。

### `GET /api/jobs/{jobId}/logs?afterId={lastLogId}`

返回常规响应信封，`data` 为按 ID 升序排列的 `JobLog[]`。`afterId` 默认 `0`，只返回 ID 大于该值的日志，一次最多 500 条；应把最后一条日志的 `id` 作为下一次请求的 `afterId`。非整数参数返回 `400`，Job 不存在返回 `404`。

### `GET /api/jobs/{jobId}/calls/{callId}`

返回指定 Job 的一次外部 HTTP 调用记录。`callId` 不属于该 Job 或不存在时返回 `404`。

`data` 的字段包括：

| 字段 | 说明 |
| --- | --- |
| `id`、`jobId`、`taskId`、`attempt`、`step` | 调用归属与执行上下文 |
| `method`、`url` | 外部请求方法和地址 |
| `requestHeaders`、`requestBody` | 已脱敏的请求记录 |
| `responseStatus`、`responseHeaders`、`responseBody` | 已脱敏的响应记录 |
| `responseTruncated` | 响应审计内容是否因大小限制而截断 |
| `durationMs`、`status` | 耗时与 `running` / `success` / `failed` 状态 |
| `errorType`、`errorMessage` | 失败信息；成功时为 `null` |
| `startedAt`、`finishedAt` | ISO 8601 时间；未完成时 `finishedAt` 为 `null` |

审计记录会遮蔽令牌、Cookie、密码、证件号、卡号和手机号等敏感值，因此它不能用于恢复原始报文。

### 5.1 实时日志 SSE

#### `GET /api/jobs/{jobId}/logs/stream?afterId={lastLogId}`

该接口通过 ASGI 直接提供 SSE，响应头为 `Content-Type: text/event-stream; charset=utf-8`。`afterId` 的含义和增量日志接口相同，默认为 `0`；非法值返回 `400`，Job 不存在返回 `404`，错误响应使用常规 JSON 错误信封。

事件格式：

```text
event: log
data: {"id":12,"jobId":7,"level":"INFO","step":"validate",...}

event: status
data: {"status":"running","progress":40}
```

- `log` 的数据结构为 `JobLog`；每轮最多补发 500 条。
- `status` 在状态或进度变化时发送。
- 连接空闲约 15 秒会发送 `: heartbeat` 注释。
- 服务端不会因 Job 进入终态自动关闭连接。客户端收到终态状态后应主动断开，并在断线重连时使用最后一个 `log.id`。

## 6. 客户端调用建议

1. 先调用产品配置接口，再构建产品申请表单和选择项。
2. 为每次“创建”操作生成并持久化幂等键；网络重试时复用同一键。
3. 创建产品申请后保存返回的 `id`，优先订阅 SSE；不可用时用 `GET /api/jobs/{id}/logs?afterId=...` 增量轮询。
4. 仅在 `failed`、`timed_out` 或 `cancelled` 后调用重试；取消 `running` Job 后持续观察直到进入终态。
5. 将 Job 详情和外部调用审计视为含敏感信息的运维数据，即使服务端已做遮蔽，也不要在不受控客户端中长期缓存。
