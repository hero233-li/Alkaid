# 身份验证交易草稿交接（2026-08-07）

目标分支：`agent/code-flow-refactor`

本提交只同步**身份验证阶段的可复用骨架与原始报文占位**，不覆盖用户内网已经继续修改并跑通的 `startApply` 主流程代码。原因是当前远程分支仍停留在“阅读协议”版本，而用户内网已经新增申请提交、返回申请编号/加密姓名/加密证件号等逻辑；直接用远程旧文件覆盖会丢失已验证的本地变更。

## 已同步

- 公共 payload/response 字段读取：`product_applications/common/values.py`
- 身份验证交易 contracts/context/use-case
- CJDK 身份 Gateway：
  - 获取 pubKey + cryptFlowNo
  - 获取加密手机号
  - Ali SDK 参数
  - 人脸活检（UAT1/UAT2 与 UATC 可选不同原始报文）
  - 发送短信
  - 校验短信
  - 最终身份验证接口骨架
- Photo 独立 `requests.Session`，与申请流程 Session 隔离
- DCPP 短信验证码日志查询 Gateway
- SM2 短信验证码加密适配点
- `identity.example.json`
- `loanIdentity.json` / `photo.json` 原始报文占位
- `messages.py` 改为自动扫描 `raw_messages/*.json`
- `.gitignore` 忽略真实 `identity.local.json`

## 当前内网主流程需要由 Codex 合并的连接点

内网现有 `execute_product_application(...)` 已经包含 `startApply`。在 `startApply` 成功、拿到：

- `application_id`
- `encrypted_customer_name`
- `encrypted_identity_no`

之后接入：

```python
identity_verification = execute_identity_verification(
    identities=identity,
    photos=identity_support.photos,
    sms_lookup=identity_support.sms_lookup,
    agreements=agreements,
    external_session=external_session,
    payload=submission.payload,
    environment=environment,
    application_id=application_submission.application_id,
    encrypted_customer_name=application_submission.encrypted_customer_name,
    encrypted_identity_no=application_submission.encrypted_identity_no,
    progress=progress,
)
```

并注意调用层必须传：

```python
identity=runtime.identity,
```

否则会出现：

```text
TypeError: execute_product_application() missing 1 required keyword-only argument: 'identity'
```

## 还需要合并的三个关键点

1. **SC00016 协议**：当前远程 `AgreementGateway` 仍是旧签名。内网 Codex 应在不破坏 SC00015 的前提下，使协议模板查询支持显式 `scene="SC00016"`。
2. **Runtime**：在用户当前已经修改过的 `CjdkJyrcRuntime` 中创建 `runtime.identity`，使用和申请流程相同的 `CjdkJyrcClient`；Photo/DCPP 使用 `IdentitySupportRuntime` 独立资源。
3. **真实接口/报文**：`identity.example.json` 中的接口 path、UAT1/UAT2 与 UATC 两份完整人脸报文、最终身份认证完整报文仍是占位，必须在内网填写。

## 流程顺序

```text
原 SC00015 阅读协议
→ startApply
→ identityGetPubKey
→ identityGetPrepareMobile
→ SC00016 阅读协议
→ 删除历史人脸照片（独立 Photo Session）
→ identityAliSdkParams
→ identityAliVideoCheck（U1/U2 与 UC 不同模板）
→ identitySmsCodeSend
→ DCPP 查询验证码
→ 使用 pubKey 做 SM2 加密
→ identitySmsCodeCheck
→ identityCardVerify
```

此提交是给本地 Codex 的继续开发基线，不代表所有真实接口参数已经最终确认。
