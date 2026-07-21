# Mock Product 协议资源

该目录只保留产品申请外系统的协议资源和底层会话能力：

- `api/`：接口、认证、Token 更新和成功码声明；
- `models/`：语义输入及响应模型；
- `raw_messages/`、`messages.py`：版本化原始报文与隔离复制；
- `client.py`：表单组装、Token Provider 和 Job 审计；
- `mock_transport.py`：Mock 外系统服务端响应。

共享登录和 Token 状态的业务会话位于 `integrations/product_system/product_application.py`。该 Session 显式赋值动态报文字段；不存在只管理 `with` 生命周期的 Adapter。

固定报文必须使用稳定版本键，通过 `new_message()` 获取深拷贝，不得修改缓存源对象，也不得保存私钥。`compile_product_config.py --check` 会校验所有 JSON 报文信封。
