# 外系统集成边界

外系统代码按系统/业务域分目录，不把 Mock 响应、业务编排和 HTTP 传输混在一起：

```text
integrations/
├── mock_product/              # 产品申请外系统
├── application_link/          # 申请链接外系统
├── business_access/           # 业务准入外系统
└── verification_approval/     # 核实审批外系统
```

每个目录的职责固定：

- `api.py` 或 `api/`：接口后缀、HTTP 方法、成功码、认证和重试声明。
- `models.py` 或 `models/`：外系统请求和响应模型。
- `adapter.py`：把后端语义输入转换为外系统调用，对业务层隐藏 HTTP 细节。
- `mock_transport.py`：只模拟外系统服务端响应；业务服务不能导入它。
- `raw_messages/`：固定长报文模板，仅由对应 Adapter 复制并显式覆盖动态字段。

`EXTERNAL_SYSTEM_MODE=mock` 时 Adapter 使用 `httpx.MockTransport`，仍然经过完整的
`EndpointExecutor -> HttpClient -> 响应模型校验` 链路。切到 `real` 时只替换 Base URL 和 Token，
业务服务、Job 和前端 API 不变。

业务准入和核实审批的 Mock 状态保存在各自 `mock_transport.py` 的内存 Store 中，用来模拟外系统
记录状态；进程重启后会清空。真实模式下状态由真实外系统维护。
