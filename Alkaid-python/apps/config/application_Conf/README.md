# 申请外系统配置

配置按性质拆成三层，禁止再次把环境地址、接口契约和运行参数放进同一个 JSON：

- `environments/`：每个环境一个文件，只维护主机/IP、端口、SSL、访问白名单及环境侧服务参数。
- `endpoints/endpoints.example.json`：集中维护全部请求契约，包括 path、method、重试策略和 Session 要求；文件内部按业务分组。
- `runtime/`：维护 mode、Java Gateway、响应限制、模板名、超时等非地址配置。

示例文件使用 `.example.json`。部署时复制为同名 `.local.json`，例如：

```text
environments/UAT1.example.json -> environments/UAT1.local.json
endpoints/endpoints.example.json -> endpoints/endpoints.local.json
runtime/application.example.json -> runtime/application.local.json
```

完整 URL 由 `environments/*` 中的 `baseUrl` 与 `endpoints/*` 中的 `path` 组合生成。
密钥不要写入这些文件，继续通过部署环境变量或密钥管理系统提供。
