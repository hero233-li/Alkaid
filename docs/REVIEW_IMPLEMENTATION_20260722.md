# 项目 Review 处理记录（2026-07-22）

本次处理以 Review 文档为输入，并遵循以下项目约束：

- 本机运行不增加登录、认证或权限校验。
- 不处理敏感信息治理。
- 不升级 MySQL、Django、Python 或其他依赖版本。
- 不增加日志脱敏，也不改变现有日志内容策略。

## 已处理

1. API 默认模拟延迟从 1000ms 调整为 0；仍可通过 `VITE_API_RESPONSE_DELAY_MS` 显式开启。
2. 不启用全局 API 进度提示，各业务页面只保留自身的加载和执行状态反馈。
3. 新增 `GET /api/meta/capabilities`，前端等待菜单显示设置和后端能力同时就绪后一次性渲染菜单，避免刷新时隐藏菜单闪现。
4. Workbench 在本机默认启用；服务端配置默认关闭，可通过 `WORKBENCH_ENABLED=true` 显式开启。
5. 任务中心由占位页改为真实任务列表，支持按状态、Job ID、名称和产品查询。
6. API 错误保留 HTTP 状态、业务错误码、Trace ID、可重试标记和详情。
7. 产品申请轮询改为串行调度，避免慢请求下 `setInterval` 重入。
8. Job 日志 DTO 补齐 `taskId` 和 `attempt`。
9. Job 步骤保存增加状态、截止时间和 Worker 执行权校验，阻止终态或旧 Worker 覆盖检查点。
10. 移动端增加导航抽屉，不再只有“隐藏侧边栏”而没有替代入口。
11. E2E 按当前“单菜单单标签”产品约定更新，重复点击菜单复用原标签并保留表单状态。

## 按项目约束保留现状

- 登录、RBAC、owner/tenant、CSRF 和管理员保护。
- 敏感字段识别、加密、保留周期和数据归属。
- 日志脱敏、请求/响应审计脱敏策略。
- MySQL、Django、Python 及依赖升级。
- 发布产物中的密钥与环境变量治理。

## 暂不实施

以下改动会改变任务投递或外部副作用语义，需要独立设计、迁移和故障演练，不适合混入本次可读性与可靠性整理：

- Transactional Outbox。
- Side Effect Ledger 与 reconciliation 状态。
- Job execution token/epoch 数据库迁移。
- Celery late ack 和 Worker 崩溃自动重投策略变更。
- HTTP 流式响应硬上限与全链路 deadline 重构。
- SSE 改造为 Redis Pub/Sub。
- 全量 OpenAPI/JSON Schema 代码生成。
- 前端依赖包体积治理；简单的 `manualChunks` 会造成 Ant Design 循环分包，需结合组件边界单独处理。

目前新增的 Job 步骤写入校验属于兼容式加固，不改变数据库结构和现有正常执行链路。
