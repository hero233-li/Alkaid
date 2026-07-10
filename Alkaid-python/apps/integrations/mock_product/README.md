# Mock Product Integration

This integration is organized for many external request payloads without using runtime templates.

Current roles:

- `api/`: endpoint definitions, auth rules, token update rules, success codes.
- `models/`: typed request inputs and response models.
- `adapters/`: business-domain call methods.
- `client.py`: shared HTTP client, token manager, executor, and Job audit wiring.
- `builders/`: external request payload construction, grouped by business area.
- `examples/`: original vendor payload examples for comparison only.

Current stage:

```text
mock_product/
├── api/
│   ├── auth.py
│   ├── application.py
│   └── audit.py
├── models/
│   ├── auth.py
│   ├── application.py
│   └── common.py
├── adapters/
│   └── application.py
├── client.py
├── builders/
│   ├── common.py
│   └── application.py
└── examples/
    └── application/
```

Builder scale rules:

- Add one `build_xxx_form()` function per external operation.
- Keep related operations in the same domain file, such as `builders/application.py`.
- Add new domain files when needed, for example `builders/customer.py`, `builders/loan.py`, or `builders/risk.py`.
- Put only repeated envelope helpers in `builders/common.py`.
- Do not add JSON templates for runtime payload construction.
- Keep raw examples grouped under `examples/<domain>/`.

As this external system grows, keep splitting by business boundary rather than by line count:

```text
mock_product/
├── api/
│   ├── application.py
│   ├── customer.py
│   └── loan.py
├── models/
│   ├── application.py
│   ├── customer.py
│   └── loan.py
├── builders/
│   ├── common.py
│   ├── application.py
│   ├── customer.py
│   └── loan.py
├── adapters/
│   ├── application.py
│   ├── customer.py
│   └── loan.py
└── examples/
    ├── application/
    ├── customer/
    └── loan/
```

`client.py` should own the shared `HttpClient`, `TokenManager`, `EndpointExecutor`, and Job audit wiring. Domain adapters should only expose calls for their domain.

Do not split only because a file is long. Split when a business boundary becomes clear, when unrelated changes start touching the same file, or when finding the right operation becomes slow.
