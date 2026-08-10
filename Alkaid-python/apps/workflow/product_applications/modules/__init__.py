"""Composable business modules for a product application workflow."""

from .application import ApplicationModuleOutcome, execute_application_module
from .identity import IdentityModuleOutcome, execute_identity_module

__all__ = (
    "ApplicationModuleOutcome",
    "IdentityModuleOutcome",
    "execute_application_module",
    "execute_identity_module",
)
