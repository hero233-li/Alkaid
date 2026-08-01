from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PROFILE_ROOT = Path(__file__).parent


class IntegrationProfileError(ValueError):
    pass


class IntegrationProfileSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=255)
    version: int = Field(ge=1)
    template: dict[str, Any]
    secretBindings: dict[str, str] = Field(default_factory=dict)


class IntegrationProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    version: int
    checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    template: dict[str, Any]
    secret_bindings: dict[str, str]


def load_integration_profile(
    profile_id: str,
    version: int,
    profile_root: Path | None = None,
) -> IntegrationProfile:
    if profile_root is None:
        return _load_default_integration_profile(profile_id, version)
    return _load_integration_profile(profile_id, version, profile_root)


@cache
def _load_default_integration_profile(profile_id: str, version: int) -> IntegrationProfile:
    return _load_integration_profile(profile_id, version, PROFILE_ROOT)


def clear_integration_profile_cache() -> None:
    _load_default_integration_profile.cache_clear()


def _load_integration_profile(
    profile_id: str,
    version: int,
    profile_root: Path,
) -> IntegrationProfile:
    matches: list[tuple[Path, IntegrationProfileSource, dict[str, Any]]] = []
    for path in sorted(profile_root.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            source = IntegrationProfileSource.model_validate(raw)
        except (OSError, ValueError) as exc:
            raise IntegrationProfileError(f"Integration Profile 无效：{path.name}: {exc}") from exc
        if source.id == profile_id and source.version == version:
            matches.append((path, source, raw))

    if not matches:
        raise IntegrationProfileError(f"未知 Integration Profile：{profile_id}@{version}")
    if len(matches) > 1:
        names = ", ".join(path.name for path, _, _ in matches)
        raise IntegrationProfileError(f"Integration Profile 重复：{profile_id}@{version}: {names}")

    _, source, raw = matches[0]
    encoded = json.dumps(
        raw,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    checksum = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    return IntegrationProfile(
        id=source.id,
        version=source.version,
        checksum=checksum,
        template=source.template,
        secret_bindings=source.secretBindings,
    )
