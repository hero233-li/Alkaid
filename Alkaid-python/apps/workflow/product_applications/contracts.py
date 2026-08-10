from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubmittedApplication:
    """Stable output contract from application submission to identity verification."""

    application_id: str
    encrypted_customer_name: str
    encrypted_identity_no: str
