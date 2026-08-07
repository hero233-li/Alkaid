from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class RequiredValueError(RuntimeError):
    pass


def optional_text(source: Mapping[str, Any], key: str) -> str | None:
    value = source.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def required_text(
    source: Mapping[str, Any],
    key: str,
    label: str | None = None,
) -> str:
    value = optional_text(source, key)
    if value is None:
        raise RequiredValueError(f"缺少{label or key}：{key}")
    return value


def required_first_text(
    source: Mapping[str, Any],
    keys: Sequence[str],
    label: str,
) -> str:
    for key in keys:
        value = optional_text(source, key)
        if value is not None:
            return value
    raise RequiredValueError(f"缺少{label}：候选字段={', '.join(keys)}")


def required_response_text(
    source: Mapping[str, Any],
    *keys: str,
    label: str | None = None,
) -> str:
    for key in keys:
        value = optional_text(source, key)
        if value is not None:
            return value
    display = label or "/".join(keys)
    raise RequiredValueError(f"外系统响应缺少{display}：候选字段={', '.join(keys)}")
