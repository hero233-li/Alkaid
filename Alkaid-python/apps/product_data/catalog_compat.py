from typing import Any


def upgrade_legacy_execution_snapshot(value: Any) -> Any:
    """Upgrade snapshots created before execution field metadata was flattened."""
    if not isinstance(value, dict):
        return value
    data = dict(value)
    definitions = data.pop("field_definitions", None)
    source_names: dict[str, str] = {}
    definition_required: list[str] = []
    if isinstance(definitions, dict):
        for name, raw_field in definitions.items():
            if not isinstance(raw_field, dict):
                continue
            source = str(raw_field.get("source") or f"application.{name}")
            source_name = source.rsplit(".", 1)[-1]
            source_names[name] = source_name
            if raw_field.get("required"):
                definition_required.append(source_name)

    data["fields"] = tuple(
        source_names.get(str(name), str(name)) for name in data.get("fields", ())
    )
    required = data.get("required_fields") or definition_required
    data["required_fields"] = tuple(source_names.get(str(name), str(name)) for name in required)
    data.setdefault("product_type", "legacy")
    data.setdefault("switch_field", data.get("switch_payload_field", ""))
    data.pop("handler", None)
    data.pop("operation", None)
    data.pop("switch_payload_field", None)
    return data
