from apps.utils.http import config
from apps.utils.http.config import get_identity_settings
from apps.utils.http.contracts import IntegrationObserver
from apps.workflow.product_applications.cjdk.client import CjdkClient
from apps.workflow.product_applications.identity.dcpp import DcppClient
from apps.workflow.product_applications.identity.photo import PhotoClient


class ProductApplicationRuntime:
    def __init__(
        self,
        *,
        settings: config.CjdkJyrcSettings,
        observer: IntegrationObserver,
        trace_id: str,
        environment: str,
    ) -> None:
        self.settings = settings
        self.observer = observer
        self.trace_id = trace_id
        self.client = CjdkClient(
            settings=settings,
            observer=observer,
            trace_id=trace_id,
            environment=environment,
        )
        self.identity_settings = get_identity_settings(settings.mode)
        self.photo_client = None
        self.dcpp_client = None
        if not self.identity_settings.mock:
            self.photo_client = PhotoClient(
                self.identity_settings.photo_environment(environment)
            )
            self.dcpp_client = DcppClient(self.identity_settings.sms_lookup)

    def open(self) -> None:
        self.client.open()
        try:
            if self.photo_client is not None:
                self.photo_client.open()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.photo_client is not None:
            self.photo_client.close()
        if self.dcpp_client is not None:
            self.dcpp_client.close()
        self.client.close()
