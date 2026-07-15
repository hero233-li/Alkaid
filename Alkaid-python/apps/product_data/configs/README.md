# 统一产品目录

产品页面、后端参数校验、Job 执行快照和申请链接路由使用同一套配置来源：

```text
configs/
├── reference_data.json
└── products/
    ├── product_a.json
    ├── product_b.json
    └── product_c.json
```

## reference_data.json

只维护真正跨产品共享的数据：Catalog 版本、环境选项和页面级联重置关系。

## products/*.json

每个产品文件自包含以下内容：

- 稳定产品代码、显示名称和产品类型
- 产品自己的开关字段
- 支持的环境、地区、机构和网点
- 申请方式代码和显示名称
- 页面字段、字段分组和字段适用的申请方式
- 每种申请方式的必填规则
- 申请链接功能路由

字段名直接使用产品申请 API 的 payload 名称，例如 `personName`、`dynamicAmount`。
必填规则只维护 `requiredFor`；页面的 `required` 由 Catalog 自动派生，避免双重配置。
外系统字段名和原始报文不属于产品配置，必须保留在 `apps/integrations/<system>/`。

## 运行方式

`apps.product_data.catalog.load_product_catalog()` 扫描 `products/*.json`，通过 Pydantic 校验后：

1. 派生前端 `ProductApplicationConfig`
2. 直接为新 Job 冻结产品和申请方式快照
3. 解析产品自己的申请链接路由

默认目录的 Catalog 和前端派生配置会在进程内缓存。修改 JSON 后需要重启 Web、Worker 和 Beat，
保证三个进程使用同一个配置版本；正在排队的 Job 仍使用创建时冻结的快照。

运行时不再读取 `product_application.json`、`execution/source/` 或编译后的 Catalog 文件。

检查配置：

```bash
python scripts/compile_product_config.py --check
```

命令名称为兼容旧开发脚本而保留；它不再生成运行时文件，会同时校验统一产品目录、每个产品的
外系统检查接口覆盖关系，以及全部原始报文的信封结构。

## 新增产品

1. 在 `products/` 新增一个产品 JSON。
2. 在对应 Integration 的 `api/` 中为产品登记外系统检查接口；若多个产品确实共用同一接口，
   可以直接复用同一个 `EndpointSpec`。配置检查会阻止遗漏或多余映射进入发布版。
3. 如果调用顺序与现有产品相同，不需要新增 Handler、注册表或业务类。
4. 只有调用顺序真正不同，才在 `product_applications/services.py` 新增一个明确业务函数；
   不为只修改常量的产品建立 Handler 或注册表。
5. 外系统请求报文仍在对应 Integration Adapter 中显式赋值。
6. 运行配置检查和后端测试。

创建 Job 时会保存 `execution_config_snapshot`。字段和申请方式配置更新后，历史 Job 仍使用创建
时的快照；旧快照中的历史 Handler/operation 字段会被兼容读取但不再参与新任务执行。
