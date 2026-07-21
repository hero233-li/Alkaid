# 外系统集成边界

产品数据相关外系统统一从 `product_system/` 暴露普通操作函数：

```text
product_system/
├── config.py                 # Base URL 与 Token 解析
├── client.py                 # 唯一 HttpClient 工厂
├── wire.py                   # 五字段和 REQ_MESSAGE 外壳
├── application_link.py
├── product_application.py    # 共享 Token 的有状态 Session
├── business_access.py
├── verification_approval.py
├── card_status.py
└── loan_status.py
```

原业务目录中的 `api.py`、`models.py`、`mock_transport.py` 仍分别保存协议声明、类型和 Mock 服务端行为；业务 Service 不能直接导入 Mock。

默认不创建 Adapter 类。普通调用函数负责创建共享 Client、执行 `EndpointExecutor`、记录 `JobApiCall` 并关闭 Client。产品申请因登录、检查、Token 轮换、提交和审计共享会话状态，保留 `ProductApplicationSession`。

`EXTERNAL_SYSTEM_MODE=mock` 仍经过完整的 `EndpointExecutor -> HttpClient -> 响应模型校验` 链路。切到 `real` 时由 `config.py` 读取各能力的 Base URL 和 Token，业务编排和前端 API 不变。

当前仓库没有可执行 Java 包、命令配置或已确认的 Java 协议，因此申请链接仍走现有 HTTP 协议。取得真实 Java 合约后，JavaGateway 只能负责 JSON 文件、子进程调用和 stdout 解析，不得包含产品流程或 Job 状态逻辑。
