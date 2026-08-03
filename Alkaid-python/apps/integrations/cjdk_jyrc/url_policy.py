from __future__ import annotations

from urllib.parse import urlsplit

from apps.integrations.cjdk_jyrc.config import UrlPolicy


class UnsafeExternalUrl(ValueError):
    pass


def validate_external_url(
    url: str,
    policy: UrlPolicy,
    *,
    previous_url: str | None = None,
) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeExternalUrl(f"外系统 URL 无效：{exc}") from exc
    if parsed.username or parsed.password:
        raise UnsafeExternalUrl("外系统 URL 禁止包含用户名或密码")
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    effective_port = port or (443 if scheme == "https" else 80)
    if scheme not in policy.allowed_schemes:
        raise UnsafeExternalUrl(f"外系统 URL scheme 未获允许：{scheme or 'missing'}")
    allowed_hosts = {item.lower().rstrip(".") for item in policy.allowed_hosts}
    if host not in allowed_hosts:
        raise UnsafeExternalUrl(f"外系统 URL host 未获允许：{host or 'missing'}")
    if effective_port not in policy.allowed_ports:
        raise UnsafeExternalUrl(f"外系统 URL port 未获允许：{effective_port}")
    if previous_url and not policy.allow_cross_host_redirect:
        previous_host = (urlsplit(previous_url).hostname or "").lower().rstrip(".")
        if host != previous_host:
            raise UnsafeExternalUrl(f"外系统重定向到不同 host：{previous_host} -> {host}")
    return url


def may_forward_session_headers(url: str, policy: UrlPolicy) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host in {item.lower().rstrip(".") for item in policy.forward_session_headers_to_hosts}
