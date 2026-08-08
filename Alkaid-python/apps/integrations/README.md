# 公共集成基础层

这里只保留跨功能稳定复用的基础设施：

- `contracts.py`：HTTP、重试和 Observer 公共类型。
- `http.py`：基于 httpx 的 HTTP Client、重试和响应限制。
- `mock.py`：通用 `MockTransportRouter`、路由匹配、响应与请求解析辅助。

这里不得出现 CJDK、申请、协议、身份、人脸、短信等业务名称或业务响应。业务 Mock 与外部系统适配器
由各功能 App 自己维护。只有出现至少两个真实消费者时，公共能力才进入此目录。
