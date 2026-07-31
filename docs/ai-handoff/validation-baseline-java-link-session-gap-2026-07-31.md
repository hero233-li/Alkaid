# Validation baseline: Java link succeeds, Session initialization incomplete

Date: 2026-07-31
Branch: `agent/code-flow-refactor`

## Purpose

This commit is the retained validation baseline for subsequent product-application work.

## Confirmed working path

```text
product JSON applicationLinks
-> deepcopy payload
-> apply payloadBindings
-> GenerateApplicationLinkRequest.external_request()
-> UTF-8 temporary request.json
-> Java args[0]
-> parse final ALKAID_RESULT
-> ApplicationLinks(internal_url, external_url)
-> GET selected application URL
```

The real environment reached the application page successfully and JavaGateway returned the application link.

## Known limitation at this baseline

Session handling is still the simplified implementation:

```text
GET application URL
-> follow redirects
-> retain Cookie jar and selected response headers
-> treat Cookie/header presence as Session established
```

The complete auth/token initialization is not implemented yet. The expected future path is:

```text
parse auth from generated link
-> choose environment-specific internal endpoint
-> call the missing initialization interface
-> exchange auth for client TokenId/session
-> retain token_id, JSESSIONID and required response headers
-> call agreement endpoints
```

## Observed real-environment result

The subsequent agreement query returned HTTP 200 with a business failure indicating that obtaining the client TokenId failed. This is the expected known failure for this baseline and must not be mistaken for a JavaGateway link-generation failure.

## Baseline rule

Future Session and agreement changes must be compared against this commit. JavaGateway request construction, product-local payload binding and successful application-link generation must continue to work unchanged.

## Validation status

This marker records the user-observed real-environment state. The GitHub connector did not execute the Django, Celery, Java SDK or intranet tests.
