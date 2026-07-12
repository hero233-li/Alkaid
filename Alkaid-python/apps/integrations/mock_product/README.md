# Mock Product Integration

This integration follows the production-style raw-message workflow used by the project.

Current roles:

- `api/`: endpoint suffixes, auth rules, token update rules and success codes.
- `models/`: semantic inputs and typed response models.
- `raw_messages/`: fixed vendor request messages grouped by business area.
- `messages.py`: cached loading plus an isolated deep copy for each call.
- `adapters/`: explicit per-operation field assignment and business-facing methods.
- `client.py`: common `payload`/`req_message` form assembly, tokens and Job audit wiring.

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
├── messages.py
├── mock_transport.py
└── raw_messages/
    └── application.json
```

Message scale rules:

- Keep fixed vendor messages in `raw_messages/<domain>.json`.
- Give deployed messages stable versioned keys such as `product_apply_v1`.
- Load with `new_message()` and assign changing fields explicitly in the domain adapter.
- Never mutate the cached source object and never put private keys in raw message files.
- Keep the outer `payload`/`req_message` assembly in `client.py`.
- `compile_product_config.py --check` validates every JSON template, including messages not yet reached by
  the current demo flow.

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
├── adapters/
│   ├── application.py
│   ├── customer.py
│   └── loan.py
└── raw_messages/
    ├── application.json
    ├── customer.json
    └── loan.json
```

`client.py` owns common transport behavior. Domain adapters own the unavoidable per-message assignments; no
generic mapping DSL or processor registry is introduced.

`mock_transport.py` owns mock external responses. It is intentionally not imported by the product business
service, so switching to a real Base URL does not change product application logic.

Do not split only because a file is long. Split when a business boundary becomes clear, when unrelated changes start touching the same file, or when finding the right operation becomes slow.
