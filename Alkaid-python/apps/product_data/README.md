# 稳定产品目录

`catalog.py` 只负责产品定义、JSON 配置读取、缓存、UI 投影和 Job 冻结快照模型；`configs/` 保存产品
JSON。这里不包含 View、Task、申请流程或外部系统实现，也不能反向依赖功能 App。

产品申请位于同级 `apps/product_applications`。后续业务以新的同级 App 接入，例如
`apps/business_access`、`apps/loan_status`、`apps/card_status`，不能继续向本目录添加业务文件。
