from __future__ import annotations

from apps.integrations.cjdk_jyrc.loan_step.identity_config import IdentitySettings
from apps.integrations.cjdk_jyrc.photo.client import PhotoClient
from apps.integrations.cjdk_jyrc.photo.gateway import CjdkPhotoGateway
from apps.integrations.cjdk_jyrc.sms_lookup.gateway import DcppSmsCodeLookupGateway


class IdentitySupportRuntime:
    """Own external resources that MUST NOT share the CJDK application session."""

    def __init__(self, *, settings: IdentitySettings, environment: str) -> None:
        self._environment = environment.upper()
        photo_settings = settings.photo_environment(self._environment)
        self._photo_client = PhotoClient(photo_settings)
        self.photos = CjdkPhotoGateway(
            client=self._photo_client,
            settings=photo_settings,
        )
        self.sms_lookup = DcppSmsCodeLookupGateway(settings.sms_lookup)

    def __enter__(self) -> "IdentitySupportRuntime":
        self._photo_client.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._photo_client.__exit__(*args)
        self.sms_lookup.close()
