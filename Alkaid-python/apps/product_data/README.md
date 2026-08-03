# 产品数据业务域

当前后端只保留 `product_applications/` 产品申请垂直切片，通过异步 Job 调用
`integrations/cjdk_jyrc/`。目录内维护自己的 Schema、函数式 Use Case、冻结结果 DTO、校验、
快照准备、Presenter、Task 和 View，不共享大而全的业务处理器。

一次请求的固定方向为：

```text
前端 -> product_data/<domain>/views.py
     -> <domain>/use_cases.py
     -> application_link_use_case.py / agreement_use_case.py
     -> validation.py / preparation.py / presenter.py
     -> integrations/<system>/runtime.py（共享基础设施生命周期）
     -> integrations/<system>/*_gateway.py（按能力转换报文）
     -> HttpClient
     -> mock_transport.py 或真实外系统
```

`contracts.py` 只定义小型能力 Protocol：申请链接、外部 Session、协议，以及基础设施 Runtime。
`execute_product_application` 在校验通过后依次组合子 Use Case，并由 `presenter.py` 保持原响应契约。
异步域由 View 创建 Job、Task 组装 Runtime 和能力 Gateway，通过公共 `jobs` 模块保存状态、日志和
外系统调用审计。

未来接入 `business_access` 时，在明确接口规格后创建独立的 `business_access/` 垂直业务包，定义它
自己的 Gateway Protocol、函数式 Use Case、冻结 Outcome 和 Integration 能力适配器，再由 Task
组合；不要向现有协议 Gateway 塞入无关方法，也不要创建占位 Step、Context 或字符串 Pipeline。
