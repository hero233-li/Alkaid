# Product application agreement flow

The product-application backend currently implements the following real protocol order:

```text
queryAgreementTemplateInfoListEA.do
-> queryPreviewImage.ajax
-> showDocumentByDocIdList.ajax
```

Execution order is controlled by `execute_product_application()`. JSON files contain fixed
request message shapes only and never contain workflow steps.

## Environment routing

The frontend sends `payload.environment`, for example `uat1`. In real mode the backend resolves
it through:

```env
CJDK_JYRC_BASE_URLS={"uat1":"http://uat1-host:8090","uat2":"http://uat2-host:8090"}
```

The environment mapping is the only place where the host and port are configured. Endpoint paths
remain stable and are defined in `apps/integrations/cjdk_jyrc/api.py`.

Real intranet IP addresses must be kept in `.env.local` or the deployment environment and must
not be committed.

## Request form

Every endpoint is sent as `application/x-www-form-urlencoded` with:

```text
msg_id
sign
timestamp
REQ_MESSAGE
biz_content
```

`REQ_MESSAGE` and `biz_content` contain the same compact JSON string. `msg_id` and timestamp are
generated per request. The captured browser request showed an empty `sign`, so the implementation
defaults to an empty value and exposes `CJDK_JYRC_FORM_SIGN` for later confirmation.

## Session handling

One `CjdkJyrcClient` and one underlying `httpx.Client` are reused for all three calls in the same
Job attempt. Cookies returned through `Set-Cookie`, including `token_id` and `JSESSIONID`, are
automatically sent on the next call.

The client also captures and forwards these response headers when returned:

```text
X-Token
X-FCOS-SESSIONID
X-Sd
```

Their values are treated as sensitive and are masked from Job API-call logs.

## Runtime context

The frozen `ProductApplicationOutcome` stores only the completed output:

```text
agreement_templates
agreement_preview
agreement_documents
session_established
session_header_names
```

The decoded PDF/base64 content remains in the in-memory Context while the Flow runs. The Job result
stores document metadata and decoded byte size, not the full base64 file.

## Fields confirmed from the supplied captures

Query agreement:

```text
x-channel
scene
selbProdId
branchId
prodSubdvDmsn
prodSubdvDmsnEncode
```

Query preview:

```text
authVariableList
selbProdId
businessNo
fcosTemplateNoList
coprProjeId
prodSubdvDmsnEncode
```

Read document:

```text
x-channel
docId
TransCode
```

Optional frontend payload fields accepted by the backend:

```text
idType
projectId
```

When omitted, they fall back to `CJDK_JYRC_DEFAULT_ID_TYPE` and
`CJDK_JYRC_DEFAULT_PROJECT_ID`.

## Validation still required

The following items need confirmation in the intranet environment:

- whether `sign` is always empty or needs a signing implementation;
- exact values for each environment URL;
- exact cooperation-project and ID-type values;
- whether all three response headers must be forwarded;
- whether multiple preview documents should be read sequentially;
- whether the real response includes `fcosTemplateNo` in the template list.
