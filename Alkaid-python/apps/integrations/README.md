# 外系统集成边界

当前产品申请主链路由 Celery Task 组装：

```text
Job 冻结快照
→ Task 创建 JobIntegrationObserver 与 CjdkJyrcAdapter
→ ProductApplicationFlow（中立 Command / Result / Port）
→ CjdkJyrcAdapter（CJDK 报文转换）
→ JavaApplicationLinkGateway / CjdkJyrcClient
→ HttpClient
```

`product_data/product_applications` 不导入 CJDK 响应模型；`integrations/cjdk_jyrc` 不导入产品
Catalog、产品配置或 Job ORM。Task 是唯一允许同时引用业务、Integration 与 Job 基础设施的组装层。

JavaGateway 基线保持为：冻结快照生成完整 Java 请求，写入 UTF-8 临时 `request.json`，文件路径是
Java 主类唯一业务参数；cwd、classpath、输出编码、超时和 `ALKAID_RESULT=` 解析均由部署配置控制。

通用 `HttpClient` 只处理传输、HTTP 状态、响应读取/解析、大小限制、重试和 Observer；CJDK 的
`biz_state`/`rsp_code`/`rsp_msg` 在 `cjdk_jyrc/response.py` 中解释。CJDK POST 当前均为
`RetryMode.NEVER`。

Session 真实初始化接口尚未实现。现有代码只安全打开申请链接并按环境 `SessionRequirement` 判断
`not_started`、`page_opened`、`partial`、`established`、`failed` 状态；未满足要求时禁止查询协议。
真实 TokenId 接口资料确认后，只在 `CjdkJyrcAdapter.initialize_session()` 或专用 Session Client
中接入，Flow 不感知其字段和路径。

响应限制集中在 `responseLimits`：JSON/HTML 原始响应、重定向次数、模板/预览数量、Base64 字符、
单文档解码大小和累计文档大小。真实 Java SDK 与内网协议接口仍需在对应网络环境验证。
