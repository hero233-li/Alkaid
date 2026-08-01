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
- 申请链接路由、真实业务报文模板和 payloadBindings

字段名直接使用产品申请 API 的 payload 名称，例如 `personName`、`dynamicAmount`。
必填规则只维护 `requiredFor`；页面的 `required` 由 Catalog 自动派生，避免双重配置。
执行字段同时声明 `valueType`（`string`、`boolean`、`integer`、`decimal`、`enum`），并可配置
`nullable`、`strip`、长度、正则、数值上下限和 `allowedValues`。后端严格区分 bool/string/int，
不做字符串与布尔、数字之间的隐式转换；验证返回新 payload，不修改调用方对象。
产品专属的外系统业务字段（例如 `order_no`、`cooperator_id`）直接保留在产品路由的
`requestTemplate` 中；公共协议骨架和敏感字段路径由
`apps/integrations/cjdk_jyrc/profiles/` 维护。产品 JSON 不允许保存 appId、私钥、公钥、Token、
Cookie、证书或 Java SDK 路径。

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

命令名称为兼容旧开发脚本而保留；它不再生成运行时文件，会同时校验统一产品目录和当前
CJDK-JYRC 协议原始报文的结构。

## 新增产品

1. 在 `products/` 新增一个产品 JSON。
2. 为每个支持的环境和申请方式配置唯一 `applicationLinks` 路由，复用对应版本的
   Integration Profile。
3. 如果调用顺序与现有产品相同，不需要新增 Handler、注册表或业务类。
4. 只有调用顺序真正不同，才在 `product_applications/services.py` 新增一个明确业务函数；
   不为只修改常量的产品建立 Handler 或注册表。
5. 产品业务报文写入路由 `requestTemplate`；敏感值只通过 Profile 的 `secretBindings` 在执行时注入。
6. 运行配置检查和后端测试。

创建 Job 时会将标准化 payload、申请链接路由、Profile 版本/校验和、编译后的非敏感模板及绑定
保存到 `execution_config_snapshot`。Worker 不再读取当前产品目录。缺少完整冻结配置的旧 Job 会
明确失败并要求重新创建，不会用当前配置静默补齐。
