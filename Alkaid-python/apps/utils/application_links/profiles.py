from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path

from .contracts import ApplicationConfigurationError, IntegrationProfile

PROFILE_ROOT = Path(__file__).parents[2] / "config" / "raw_messages"


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


def _load_integration_profile(
    profile_id: str,
    version: int,
    profile_root: Path,
) -> IntegrationProfile:
    matches: list[tuple[Path, IntegrationProfile]] = []
    for path in sorted(profile_root.glob("application_link_*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            encoded = json.dumps(
                raw,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            profile = IntegrationProfile.model_validate(
                {**raw, "checksum": f"sha256:{hashlib.sha256(encoded).hexdigest()}"}
            )
        except (OSError, ValueError) as exc:
            raise ApplicationConfigurationError(
                f"Integration Profile 无效：{path.name}: {exc}"
            ) from exc
        if profile.id == profile_id and profile.version == version:
            matches.append((path, profile))
    if not matches:
        raise ApplicationConfigurationError(f"未知 Integration Profile：{profile_id}@{version}")
    if len(matches) > 1:
        names = ", ".join(path.name for (path, _) in matches)
        raise ApplicationConfigurationError(
            f"Integration Profile 重复：{profile_id}@{version}: {names}"
        )
    return matches[0][1]
