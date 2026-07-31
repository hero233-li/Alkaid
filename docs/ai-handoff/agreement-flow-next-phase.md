# 产品申请：申请链接、Session 与阅读协议实现记录

## 当前分支

- Repository：`hero233-li/Alkaid`
- Branch：`agent/code-flow-refactor`
- 产品申请后端是当前唯一保留的 `product_data` 业务入口。

## 已实现执行顺序

`ProductApplicationFlow.execute()` 直接通过 Python 方法顺序控制：

```text
parse_submission
-> load_execution_snapshot
-> validate_submission
-> generate_application_link
-> acquire_application_session
-> query_agreement_templates
-> query_agreement_preview
-> read_agreement_documents
-> build_result
```

JSON 不保存步骤、Handler 名称或下一步信息。

## 申请链接

产品配置中原有的：

```json
{
  "features": {
    "applicationLinks": [
      {"environment": "env-1", "category": "动态链接"}
    ]
  }
}
```

只用于确定当前产品和环境应生成“动态链接”还是“太阳码”。

链接生成请求沿用五字段 Form：

```text
msg_id
sign
timestamp
REQ_MESSAGE
biz_content
```

`REQ_MESSAGE` 与 `biz_content` 是同一份紧凑 JSON，业务主体包含：

```text
env
product
category
cooperationProjectId（存在时）
payload
```

生成结果包含 `internal_url` 与 `external_url`。Flow 根据：

```env
APPLICATION_LINK_URL_MODE=internal
```

选择需要打开的地址。

## Session

`CjdkJyrcClient` 在一个 Job attempt 内只创建一个底层 `httpx.Client`：

1. 使用选中的申请链接执行 GET；
2. 自动跟随 301/302；
3. 保存跳转过程中产生的 Cookie；
4. 捕获 `X-Token`、`X-FCOS-SESSIONID`、`X-Sd`；
5. 只有确认 Session 已建立后，才允许调用协议接口；
6. 查询、预览、阅读协议全部复用同一个 Client。

Cookie、Token、Session Header、完整申请链接和 PDF Base64 均不会以明文写入 Job 日志或 Job 结果。

## 协议接口

```text
POST /h5/microservice/queryAgreementTemplateInfoListEA.do
POST /h5/microservice/queryPreviewImage.ajax
POST /h5/microservice/showDocumentByDocIdList.ajax
```

固定请求报文在：

```text
Alkaid-python/apps/integrations/cjdk_jyrc/raw_messages/agreement.json
```

Adapter 显式填写机构、客户身份、合作项目、模板编号和 docId 等动态字段。

## 环境路由

前端通过 `payload.environment` 传环境代码，例如 `uat1`。

链接生成系统与协议系统可以分别配置 IP 和端口：

```env
APPLICATION_LINK_BASE_URLS={"uat1":"http://link-uat1-host:8090"}
CJDK_JYRC_BASE_URLS={"uat1":"http://agreement-uat1-host:8090"}
```

接口路径固定，基础 URL 按环境选择。真实内网地址只放 `.env.local` 或部署环境变量，不提交 Git。

## Context

`ProductApplicationContext` 保存：

```text
submission
execution_snapshot
application_link_category
application_links
selected_application_link_kind
agreement_templates
agreement_preview
agreement_documents
session 状态摘要
result
```

Context 不保存工作流 steps，也不持久化 Cookie、Token 或完整 PDF Base64。

## 内网验证

```powershell
cd Alkaid-python
python manage.py check
python -m pytest tests/test_product_application_flow.py tests/test_api.py tests/test_runtime_mode.py -q
python -m pytest -q
ruff check .
ruff format --check apps/integrations/cjdk_jyrc apps/product_data/product_applications tests/test_product_application_flow.py tests/test_api.py
```

真实模式还需确认：

- 各环境的两个基础 URL；
- 链接生成接口真实路径与签名函数；
- 后端应选择 internal 还是 external URL；
- 打开链接是否确实为 GET 并允许自动跳转；
- 产品 JSON 中环境代码与前端环境代码一致；
- `projectId`、`idType` 的真实值；
- 协议响应的多文档行为。
