from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel

from apps.integrations.contracts import AuthSpec, HttpResult, TokenSource, TokenUpdateSpec


class TokenUnavailable(RuntimeError):
    pass


class TokenUpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class TokenState:
    value: str
    version: int
    expires_at: datetime | None = None


class TokenProvider(Protocol):
    def get(self) -> TokenState: ...

    def update(self, value: str, *, expires_at: datetime | None = None) -> TokenState: ...


class FlowTokenProvider:
    """Mutable token state scoped to one Job attempt; never share between workers."""

    def __init__(self) -> None:
        self._state: TokenState | None = None

    def get(self) -> TokenState:
        if self._state is None:
            raise TokenUnavailable("流程 Token 尚未获取")
        return self._state

    def update(self, value: str, *, expires_at: datetime | None = None) -> TokenState:
        token = value.strip()
        if not token:
            raise TokenUpdateError("不能使用空 Token 更新流程认证状态")
        version = 1 if self._state is None else self._state.version + 1
        self._state = TokenState(value=token, version=version, expires_at=expires_at)
        return self._state


class StaticTokenProvider:
    def __init__(self, value: str) -> None:
        token = value.strip()
        if not token:
            raise TokenUnavailable("固定 Token 未配置")
        self._state = TokenState(value=token, version=1)

    def get(self) -> TokenState:
        return self._state

    def update(self, value: str, *, expires_at: datetime | None = None) -> TokenState:
        raise TokenUpdateError("固定 Token 不允许由接口响应更新")


class TokenManager:
    def __init__(self, providers: dict[str, TokenProvider]) -> None:
        self._providers = dict(providers)

    def build_headers(self, auth: AuthSpec | None) -> dict[str, str]:
        if auth is None:
            return {}
        state = self._provider(auth.provider).get()
        return {auth.header: f"{auth.prefix}{state.value}"}

    def apply_update(
        self,
        spec: TokenUpdateSpec | None,
        result: HttpResult[BaseModel],
    ) -> TokenState | None:
        if spec is None:
            return None
        source: Any
        if spec.source == TokenSource.RESPONSE_HEADER:
            source = {key.lower(): value for key, value in result.headers.items()}
            value = source.get(spec.path.lower())
        else:
            source = result.body
            value = _read_path(source, spec.path)
        if not isinstance(value, str) or not value.strip():
            raise TokenUpdateError(
                f"接口成功但未在 {spec.source.value}:{spec.path} 中返回有效 Token"
            )
        return self._provider(spec.provider).update(value)

    def state(self, provider: str) -> TokenState:
        return self._provider(provider).get()

    def _provider(self, name: str) -> TokenProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise TokenUnavailable(f"Token Provider 未注册：{name}") from None


def _read_path(value: Any, path: str) -> Any:
    current = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current
