import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

MESSAGE_ROOT = Path(__file__).with_name("raw_messages")


class ExternalMessageConfigurationError(ValueError):
    pass


@lru_cache(maxsize=32)
def _load_group(group: str) -> dict[str, Any]:
    path = MESSAGE_ROOT / f"{group}.json"
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExternalMessageConfigurationError(f"读取外系统原始报文失败：{path}: {exc}") from exc
    if not isinstance(content, dict):
        raise ExternalMessageConfigurationError(f"外系统原始报文必须是对象：{path}")
    _validate_group(path, content)
    return content


def new_message(group: str, code: str) -> dict[str, Any]:
    """Return an isolated mutable copy; cached source templates are never mutated."""

    try:
        message = _load_group(group)[code]
    except KeyError:
        raise ExternalMessageConfigurationError(f"外系统原始报文不存在：{group}.{code}") from None
    if not isinstance(message, dict):
        raise ExternalMessageConfigurationError(f"外系统原始报文必须是对象：{group}.{code}")
    return copy.deepcopy(message)


def validate_message_catalog() -> dict[str, int]:
    """Validate every raw-message file, including templates not used by the current flow."""

    files = sorted(MESSAGE_ROOT.glob("*.json"))
    if not files:
        raise ExternalMessageConfigurationError("没有找到外系统原始报文")
    message_count = 0
    for path in files:
        content = _load_group(path.stem)
        message_count += len(content)
    return {"groups": len(files), "messages": message_count}


def clear_message_cache() -> None:
    _load_group.cache_clear()


def _validate_group(path: Path, content: dict[str, Any]) -> None:
    if not content:
        raise ExternalMessageConfigurationError(f"外系统原始报文文件不能为空：{path}")
    for code, message in content.items():
        location = f"{path}:{code}"
        if not isinstance(code, str) or not code.strip():
            raise ExternalMessageConfigurationError(f"外系统报文代码不能为空：{path}")
        if not isinstance(message, dict):
            raise ExternalMessageConfigurationError(f"外系统原始报文必须是对象：{location}")
        for envelope_key in ("REQ_BODY", "REQ_HEAD"):
            if not isinstance(message.get(envelope_key), dict):
                raise ExternalMessageConfigurationError(
                    f"外系统原始报文缺少对象字段 {envelope_key}：{location}"
                )
