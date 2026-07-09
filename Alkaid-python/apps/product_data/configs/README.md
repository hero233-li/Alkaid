# 产品配置与 Handler 使用说明

当前后端采用“配置选择 Handler，Python 实现业务流程”的模式。

配置文件只负责产品信息、字段要求和 Handler 选择。接口调用顺序、业务判断、长请求报文和响应清洗直接写在 Python Handler 中，不再使用 JSON workflow、endpoint 和 request profile 编排。

## 1. 页面配置

文件：`product_application.json`

它控制前端可见内容：

- 环境、产品、地区、机构和网点
- 表单字段及字段组
- 产品启用哪些字段组
- 产品必填字段

前端通过以下接口读取：

```text
GET /api/product-data/applications/config
```

字段定义只写一次：

```json
{
  "name": "redShieldEnabled",
  "label": "红盾",
  "control": "switch",
  "defaultValue": true
}
```

顶层字段组：

```json
"fieldSets": {
  "customerBase": ["personName", "certificateNo", "phone", "cardNo"],
  "whitelist": ["whitelistEnabled"],
  "redShield": ["redShieldEnabled"],
  "credit": ["creditEnabled"]
}
```

产品引用字段组：

```json
{
  "value": "product-a",
  "fieldSets": ["selection", "customerBase", "enterprise", "whitelist", "redShield"],
  "requiredFields": ["personName", "certificateNo", "phone", "whitelistEnabled"]
}
```

## 2. 后端执行配置

目录：`execution/source/`

```text
execution/source/
├── manifest.json
├── fields.json
├── field_sets.json
└── products/
    ├── product_a.json
    ├── product_b.json
    └── product_c.json
```

### 2.1 manifest.json

```json
{
  "version": 5,
  "products": [
    "products/product_a.json",
    "products/product_b.json",
    "products/product_c.json"
  ]
}
```

新增或修改执行配置后，递增 `version`，然后执行：

```bash
python scripts/compile_product_config.py
```

检查源配置和编译结果：

```bash
python scripts/compile_product_config.py --check
```

运行时只读取：

```text
execution/compiled/product_catalog.json
```

新 Job 会把版本和产品配置快照保存到：

```text
execution_config_version
execution_config_snapshot
```

### 2.2 fields.json

统一定义后端业务输入字段：

```json
"customer_name": {
  "source": "application.personName",
  "required": true,
  "normalizer": "strip"
}
```

- `source`：从申请参数的哪个位置读取
- `required`：产品申请方式启用该字段后是否必填
- `normalizer`：通用数据清洗

支持的 normalizer：

```text
identity  保持原值
strip     字符串删除首尾空格
boolean   使用 Python bool(value) 转换
```

`boolean` 适合前端提交的 JSON 布尔值。非空字符串都将转换为 `true`，所以不能直接用它处理字符串 `"false"`、`"0"` 或 `"N"`。

### 2.3 field_sets.json

用于复用后端业务字段：

```json
"customer_base": [
  "customer_name",
  "certificate_no",
  "phone",
  "customer_type"
]
```

### 2.4 products/product_a.json

```json
{
  "product": {
    "code": "product-a",
    "name": "产品A",
    "product_type": "whitelist_product",
    "handler": "whitelist_application_v1",
    "default_application_method": "normal",
    "common_field_sets": ["customer_base", "organization_base"],
    "application_methods": {
      "normal": {
        "name": "普通申请",
        "operation": "mock_product.product_a.apply",
        "fields": ["whitelist_enabled", "red_shield_enabled"]
      }
    }
  }
}
```

- `product_type`：产品业务大类
- `handler`：实际执行业务流程的版本化 Python Handler
- `common_field_sets`：所有申请方式共用字段
- `application_methods`：申请方式及其额外字段
- `operation`：任务结果中的业务操作标识

配置编译时会检查 Handler 是否已经注册。

## 3. Handler

目录：

```text
apps/product_data/handlers/
├── base.py
├── products.py
└── registry.py
```

当前注册关系：

```text
whitelist_application_v1  → WhitelistApplicationHandler
red_shield_application_v1 → RedShieldApplicationHandler
credit_application_v1     → CreditApplicationHandler
```

产品配置通过 `handler` 选择处理器。Handler 直接使用 Python 表达：

- 接口调用顺序
- `if/else` 业务判断
- 提前结束
- 多接口结果组合
- 请求报文构建
- 响应字段清洗

公共流程和 `application/x-www-form-urlencoded` 示例在 `handlers/base.py`。产品差异在 `handlers/products.py`。

## 4. 多字段 form-urlencoded

公共 HTTP Client 支持：

```python
ctx.call(
    "customer.query",
    endpoint,
    {
        "req_message": {
            "req_head": {...},
            "req_body": {"request": {...}},
        },
        "bizcond": {...},
        "starttime": ctx.start_time,
        "traceno": ctx.trace_no,
    },
)
```

发送规则：

- `dict/list/tuple`：自动 `json.dumps(..., ensure_ascii=False)`
- `bool`：转换为 `true/false`
- 其他值：使用 `str(value)`
- `None`：不发送该表单字段

最终使用：

```python
httpx.request(..., data=form_data)
```

由 httpx 生成 `application/x-www-form-urlencoded`，不要手工 URL 编码。

## 5. 请求审计

每次外部调用继续写入 `JobApiCall`：

```json
{
  "query": {},
  "form": {
    "req_message": {},
    "bizcond": {},
    "starttime": "...",
    "traceno": "..."
  }
}
```

审计保存序列化前的结构化表单内容，便于查看长报文；Token、证件号、手机号、卡号等字段继续脱敏，超长内容继续按现有限制截断。

## 6. 新增产品类型

1. 在 `handler_codes.py` 增加版本化 Handler 编号。
2. 在 `handlers/products.py` 新增 Handler。
3. 在 `handlers/registry.py` 注册 Handler。
4. 新建产品配置并填写 `product_type` 和 `handler`。
5. 在 `manifest.json` 注册产品并递增版本。
6. 重新编译配置并运行测试。

不要覆盖已经被旧 Job 引用的 Handler 行为。逻辑发生不兼容变化时新增 `*_v2`，并让新产品配置引用新版本；旧 Handler 至少保留到相关 Job 超过保留期限。
