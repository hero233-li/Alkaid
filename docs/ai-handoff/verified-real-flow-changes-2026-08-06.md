# Alkaid 真实产品申请链路已确认改动

更新日期：2026-08-06  
目标分支：`agent/code-flow-refactor`  
远程基准：`c33a4a5ac9b96b9287c98b9609a293065ee844d2`

## 一、已经确认并同步的行为

### 1. 合作项目改为产品级弱绑定

- `cooperationProjectId` 允许为 `null` 或不配置。
- 产品配置了合作项目编号时，后端自动写入冻结任务参数，前端不能提交不一致的编号。
- 产品未绑定合作项目时，前后端均不提交 `cooperationProjectId`。
- 外系统报文仅在合作项目编号有值时加入 `prodSubdvDmsnEncode`。

### 2. 申请链接只校验实际使用的地址

JavaGateway 仍返回 `internal_url` 和 `external_url`，但不再在生成阶段强制校验两个地址。主流程按 `applicationLinkUrlMode` 选择一个地址后，在 Session 初始化请求前校验实际使用的 URL。

### 3. Session 使用拼接 URL 初始化

每个环境支持：

- `sessionUrlTemplate`：必须包含 `{auth}` 占位符；
- `sessionMethod`：独立配置 `GET` 或 `POST`；
- `verifySsl`：控制该环境的 HTTPS 证书校验。

真实流程为：

1. 从 JavaGateway 返回的申请链接 query 或 hash 路由中提取 `auth`；
2. 对 `auth` 重新进行 URL 编码；
3. 替换 `sessionUrlTemplate` 中的 `{auth}`；
4. 使用 `sessionMethod` 请求拼接后的 URL；
5. 保存 Session Cookie 和响应 Header。

未配置 `sessionUrlTemplate` 时保留旧行为，直接打开申请链接，避免破坏 Mock 流程和旧环境。

### 4. Session Cookie/Header 捕获

当前会识别并复用：

- Cookie：`token_id`、`JSESSIONID`、`X-FCOS-SESSIONID`；
- Header：`X-Sd`、`X-Token`、`X-FCOS-SESSIONID`。

Cookie 同时保留在 HTTP 客户端 Cookie Jar，并显式构造后续请求使用的 `Cookie` Header。Session 是否建立成功仍由环境中的 `requiredCookies`、`requiredHeaders`、`requiredAnyHeaders` 判定。

原始 Session 日志只在本机设置 `CJDK_SESSION_RAW_LOG=true` 时输出，默认关闭。

### 5. 协议请求使用当前任务产品

协议模板查询和协议预览中的 `selbProdId` 改为读取当前冻结任务参数中的 `payload.product`，不再读取全局 `CJDK_JYRC_PRODUCT_ID`。

### 6. 合作项目编号按需加入协议报文

- `cooperationProjectId` 有值：加入 `prodSubdvDmsnEncode`；
- `cooperationProjectId` 为空：从报文中彻底移除该字段，不发送 `null` 或空字符串。

### 7. 保留模板中的 `idType`

协议预览只更新模板已有 `authVariableList` 项的值。当前任务未提供 `idType` 且全局默认值为空时，保留原始报文模板中的 `0102`，避免整体重建列表导致字段丢失。

### 8. 协议阅读 docId 选择

- 顶层 `preview.doc_id` 有值时，仅使用该值读取协议；
- 顶层无值时，使用 `preview.documents` 中所有非空 `doc_id`；
- 两处都没有有效值时，明确报错。

单个 docId 使用 `(preview.doc_id,)` 创建单元素元组，避免 `tuple[...]` 产生 `GenericAlias`。

## 二、本次没有同步的内容

- `environments.local.json`：包含本机路径、真实地址和密钥，继续由 `.gitignore` 排除；只更新示例配置结构。
- 真实 appId、私钥、公钥和完整 auth/Cookie/Token 值。
- 本机尚未完整核对的业务产品 JSON 数据。
- “阅读协议之后的提交接口”：接口路径、请求报文和成功响应字段尚未确认，因此本次不加入半成品实现。
- 调试期间临时放开的整条产品申请任务重试。提交写接口接入前仍应保持外系统写任务默认不可重试。

## 三、运行注意事项

修改配置或报文后必须同时重启：

1. Django/Uvicorn 后端；
2. Celery Worker；
3. 前端开发服务（前端类型或配置适配变更时）。

验证新配置必须创建新任务。旧任务重试会继续使用旧的冻结执行快照。
