"""Backward-compatible import for the combined CJDK adapter."""

from apps.integrations.cjdk_jyrc.adapter import CjdkJyrcAdapter

CjdkJyrcApplicationLinkAdapter = CjdkJyrcAdapter

__all__ = ["CjdkJyrcApplicationLinkAdapter"]
