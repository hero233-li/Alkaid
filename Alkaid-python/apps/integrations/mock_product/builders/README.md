# Mock Product Builders

This package owns request payload construction for the mock product external system.

Rules:

- One builder function per external operation.
- Group builders by business area, such as `application.py`, `customer.py`, `loan.py`, and `risk.py`.
- Put only repeated envelope helpers in `common.py`.
- Do not read runtime payloads from template files.
- Keep raw vendor examples in `../examples/` for comparison and tests only.
