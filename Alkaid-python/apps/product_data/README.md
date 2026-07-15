# 产品数据业务域

各入口分别维护 Schema、Service、Task/View，不共享大而全的处理器：

| 业务域 | 后端目录 | 执行方式 | 外系统目录 |
| --- | --- | --- | --- |
| 产品申请 | `product_applications/` | 异步 Job | `integrations/mock_product/` |
| 申请链接 | `application_links/` | 异步 Job | `integrations/application_link/` |
| 业务准入 | `business_access/` | 异步 Job，支持查询、失效、通知查询和推送 | `integrations/business_access/` |
| 核实审批 | `verification_approval/` | 异步 Job，支持查询、领取、退回、刷新、核实项更新和快捷操作 | `integrations/verification_approval/` |
| 申请数据生成 | `application_data/` | 异步 Job，生成可校验的 Mock 客户和企业数据 | `integrations/application_data/` |
| 卡状态处理 | `card_status/` | 异步 Job，支持查询和资金/密码操作 | `integrations/card_status/` |
| 贷款状态处理 | `loan_status/` | 异步 Job，支持贷款查询、合同、凭证、还款和冻结操作 | `integrations/loan_status/` |

一次请求的固定方向为：

```text
前端 -> product_data/<domain>/views.py
     -> <domain>/services.py
     -> integrations/<system>/adapter.py
     -> HttpClient
     -> mock_transport.py 或真实外系统
```

异步域在 View 和 Service 之间增加自己的 Celery Task，并通过公共 `jobs` 模块保存状态、日志和
外系统调用审计。新增接口时只在所属业务域和对应 Integration 中修改，不向其他三个域添加分支。
