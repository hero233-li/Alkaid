# Workflow

`workflow` 用于集中放置直接面向前端的功能流程。每个子目录代表一项独立功能，并保留自己的 API、参数模型、任务和流程编排。

当前功能：

- `application_links`：申请链接获取。
- `product_applications`：产品申请。

## 目录边界

- 新增与前端交互的功能时，在此目录下新增独立子包。
- 子包负责接口适配和业务流程编排，不直接复制 Java 网关、任务基础设施等通用能力。
- 通用 HTTP 协议和客户端放在 `apps/utils/http`，Java 网关放在 `apps/utils/java`，任务通用能力放在 `apps/workflow/Jobs`。
- 不同 workflow 功能之间不直接引用私有实现；需要复用的能力应下沉到对应公共层。
