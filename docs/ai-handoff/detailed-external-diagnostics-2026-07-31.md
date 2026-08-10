# Detailed external diagnostics after Java link baseline

Date: 2026-07-31
Branch: `agent/code-flow-refactor`

## Baseline retained

The validation baseline before these logging changes is commit:

```text
1c012331c2fd9f841cf129d493b46fadf3690818
```

That baseline represents:

```text
JavaGateway application link generation succeeds
-> generated link opens successfully
-> current simplified Session check runs
-> agreement query fails because client TokenId initialization is incomplete
```

## Changes after the baseline

This version adds diagnostics only. It intentionally does not implement the missing auth/client-TokenId initialization interface yet.

### JavaGateway

- Sanitized request structure is written to JobApiCall and JobLog.
- Java working directory and command structure are logged.
- Java return code, stdout and stderr are logged with sensitive values masked.
- The final `ALKAID_RESULT` parsing behavior is unchanged.

### Session diagnostics

- Selected application URL is logged with auth/token values masked.
- Whether an `auth` query parameter exists and its length are recorded.
- Redirect chain, `Set-Cookie` presence, cookie names and forwarded response-header names are recorded.
- Logs explicitly state that the current Session check only verifies Cookie/header presence.

### Non-Java HTTP diagnostics

- Full resolved URL, request headers and structured request body are logged after masking.
- Raw response status, headers and body are stored before Pydantic validation.
- `biz_state=F` responses surface `rsp_code` and `rsp_msg` directly.
- Schema validation errors list missing fields and actual top-level response fields.

## Security

Private/public keys, identity numbers, phone numbers, cards, auth values, Tokens, Cookies, session identifiers and document Base64 are masked or omitted. The request/response structure and non-sensitive business errors remain visible.

## Next implementation step

Use the new logs to identify and implement the missing interface between application-link opening and agreement query:

```text
parse auth
-> call environment-specific initialization endpoint
-> exchange auth for client TokenId/session
-> retain token_id, JSESSIONID and required response headers
-> query agreements
```

## Validation status

Files were pushed through the GitHub connector. Django, Celery, Java SDK and intranet tests were not executed by the connector.
