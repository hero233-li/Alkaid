# 申请链接内网接入实施状态

## 已确认契约

- 一次业务提交只调用一次 `generate_link()`，不再先创建申请再生成链接。
- 太阳码调用 `/links/sun-code`，动态链接调用 `/links/dynamic`。
- 两种响应都必须同时包含 `internal_url` 与 `external_url`。
- Python 负责构造并以表单发送且仅发送五个字段：`msg_id`、`sign`、`timestamp`、`REQ_MESSAGE`、`biz_content`。
- `REQ_MESSAGE` 与 `biz_content` 使用同一份序列化字符串。
- 外层 `env`、`product`、`category`、`cooperationProjectId` 是权威字段，业务参数放入 `payload`；同名冲突会拒绝执行。
- 合作项目由后端配置下发，前端展示 `label`、提交 `value`；无配置时不展示。

成功请求样例：

- `docs/contracts/application-link/sun-code-success-request.json`
- `docs/contracts/application-link/dynamic-link-success-request.json`

## 当前工作区无法同步的内容

当前仓库没有内网新增的 Java 源码、Python SDK 源码或 Jar 文件，也没有可读取的内网目录，因此本次没有伪造这些文件。现有 Python Adapter 已提供单次五字段表单接入边界；拿到内网文件后仍需确认：

1. `sign` 的真实算法或 Java SDK/Jar 调用方式；当前仅支持配置静态 `APPLICATION_LINK_FORM_SIGN`。
2. `timestamp` 的真实格式；当前默认 `%Y%m%d%H%M%S`，可配置。
3. 两个真实路径、业务成功码以及响应字段名。
4. Java/Jar 的版本、启动参数、类路径和进程管理方式。

若内网要求签名必填，设置 `APPLICATION_LINK_SIGN_REQUIRED=true`；未提供签名时会在发送前明确失败。

## Windows 生命周期

默认启动脚本现在会清理配置端口的遗留监听进程，输出 PID 与进程名，并在退出时按进程树清理 Backend/Worker 后等待端口释放。可用 `DEV_CLEAN_STALE_PORTS=false` 禁止启动前清理。该逻辑只能在 Windows 上做最终运行验证。
