# 历史兼容清理计划

历史兼容只用于平滑升级，不作为永久业务契约。当前统一清理日期为 **2026-10-31**。

| 兼容项 | 最后产生旧数据的契约 | 最长保留周期 | 负责人 | 验证与到期处理 |
| --- | --- | --- | --- | --- |
| 点号 Job kind（如 `verification_approval.search`） | 未提供 `payload.operation` 的旧菜单版本 | `JOB_RETENTION_HOURS`，当前默认 720 小时 | 后端维护人 | 查询生产库确认无点号 kind 活跃 Job；随后只接受标准 `kind` 与 `payload.operation` |
| `application_link_generation`、`application_data.generate` | 使用旧 Job kind 别名的菜单版本 | `JOB_RETENTION_HOURS`，当前默认 720 小时 | 后端维护人 | 查询生产库确认别名 Job 已清零；随后删除 `LEGACY_KIND_ALIASES` |
| 产品执行旧快照 | 包含 `field_definitions`、`handler` 或 `switch_payload_field` 的快照版本 | Job 保留周期加一次完整内网升级窗口 | 产品数据维护人 | 扫描 `execution_config_snapshot` 确认旧字段清零；随后删除 `catalog_compat.py` |
| 前端旧产品配置转换 | 没有 `fieldSets` 或仍下发旧 control 展示字段的 Catalog | 旧前端不再部署且旧 Catalog 快照清零 | 前端维护人 | 使用当前 Catalog 编译检查并核对内网版本；随后删除 `configAdapter.ts` 中 legacy 分支 |

后端会在截止日期后主动拒绝旧 Job 契约，避免兼容分支无期限存在。验证命令至少包括 `python -m pytest`、`python scripts/compile_product_config.py --check` 和生产库只读统计。确认生产 Job、内网部署版本和 Catalog 快照均已越过保留窗口后，应使用独立提交删除兼容代码，不与结构整理混合提交。
