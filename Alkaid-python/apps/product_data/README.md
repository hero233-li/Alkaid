# 产品数据业务域

产品数据菜单采用三种固定流程，不共享大而全的 Flow、Context 或 Handler：

1. 异步外系统菜单：`View -> Job -> Task -> Service -> product_system -> HttpClient`。
2. 异步本地计算菜单：`View -> Job -> Task -> Service -> Job.result`。
3. 同步配置查询：`View -> Service -> 配置/数据库`。

| 业务域 | Job kind | `payload.operation` | Integration |
| --- | --- | --- | --- |
| 产品申请 | `product_application` | 无（单一三步流程） | `product_system/product_application.py`、`application_link.py` |
| 申请链接 | `application_link` | 无（单一生成流程） | `product_system/application_link.py` |
| 业务准入 | `business_access` | `search/invalidate/notifications/push` | `product_system/business_access.py` |
| 核实审批 | `verification_approval` | `search/claim/return/refresh/item-update/action` | `product_system/verification_approval.py` |
| 申请数据生成 | `application_data` | `generate` | 无，本地计算 |
| 卡状态处理 | `card_status` | `search/action` | `product_system/card_status.py` |
| 贷款状态处理 | `loan_status` | `search/action` | `product_system/loan_status.py` |

高频交易目前只有前端入口，仓库中没有可迁移的后端协议、模型或外系统实现；补齐真实协议后应按同一模板新增，不能用虚构响应代替。

## 菜单文件职责

- `schemas.py`：请求模型、Job payload、响应模型和操作枚举。
- `views.py`：校验请求并调用 `jobs.http.submit_async_job()`。
- `tasks.py`：只调用 `run_menu_task()`，保留菜单自己的超时配置。
- `services.py`：唯一业务编排入口，直接展示操作分支或步骤顺序。
- `urls.py`：HTTP 路由。

多操作菜单统一使用稳定 `kind`，具体动作保存在 `payload.operation`；旧的点号 kind 只在任务调度和 Service 中兼容历史 Job，不再创建。

产品申请固定执行并保存三个检查点：

```text
links -> application -> followup
```

每步完成后立即写入 `Job.result`。Worker 重跑时跳过已有步骤，失败和超时也保留已完成步骤。

核实审批查询返回的完整 `task` 是后续操作的上下文。前端在领取、退回、刷新、核实项完成/取消、一键完成、一键补件、一键提交、审批提交时把它原样放入 `context`；后端随 Job payload 保存并直接传给外系统，不再次查询。
