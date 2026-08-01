# 产品申请 P1/P2 结构与可靠性收尾

## 已实现

- Task 读取冻结快照并组装 `JobIntegrationObserver`、`CjdkJyrcAdapter` 和显式顺序 Flow。
- Flow/Context 只使用中立 Command/Result/Port，不持有完整 Job 或 CJDK 响应模型。
- Catalog 字段支持严格类型、nullable、strip、长度、正则、枚举和数值范围校验；原 payload 不修改。
- Session 使用五态模型和环境级 `SessionRequirement`；任意 Cookie 不再等于 established。
- URL Policy 校验申请链接、每次重定向、最终 URL、协议地址和 Session Header 转发 Host。
- CJDK POST 默认不重试；通用 HTTP 提供 NEVER/CONNECT_ONLY/IDEMPOTENT 和 jitter。
- JSON/HTML、模板、预览、Base64、单文档及累计文档均有限制。
- Workbench 默认关闭且关闭时不注册路由；启用时增加 Host/IP/重定向、敏感头和上传限制。
- CJDK 业务响应判断移出通用 HTTP。

## 未实现与验证边界

- 真实 auth/TokenId Session 初始化接口：契约未提供，未猜测 URL 或字段。
- 真实 Java SDK：本轮没有执行；仅保留并回归单元测试中的调用契约。
- 真实内网外系统：本轮没有连接；URL/Session 配置示例不是生产契约。
- Workbench 身份认证、用户权限、按用户历史隔离、保留期和审计：项目当前没有相应身份域，生产继续关闭。

## 清理审查表

| 字段/抽象 | 当前调用方证据 | 生产使用 | 处理 | 兼容说明 |
|---|---|---:|---|---|
| EndpointExecutor | 删除前仅 `tests/test_http_client.py` | 否 | 删除 | 能力保留在 HttpClient/具体 Adapter |
| TokenProvider/TokenManager | 删除前仅 EndpointExecutor 与其测试 | 否 | 删除 | 不为未知 Session 契约保留假认证抽象 |
| EndpointSpec auth/token/success 字段 | 删除前无调用方 | 否 | 删除 | CJDK 业务解释器显式处理 |
| cooperationProjects | reference JSON、前端 ApplicationLink 表单与测试仍引用 | 是 | 保留 | 未获得兼容删除证据 |
| resolve_application_link_base_url | 全仓无定义/引用 | 否 | 无需处理 | 当前基线已不存在 |

## JavaGateway 不变量

完整 Java 请求仍来自冻结快照；临时请求文件使用 UTF-8；Java 主类仅接收 request.json 路径；
cwd、classpath、输出编码、超时和最后一个 `ALKAID_RESULT=` 解析没有改变。
