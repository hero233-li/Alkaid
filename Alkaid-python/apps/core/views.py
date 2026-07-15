import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import FileResponse, Http404, JsonResponse
from django.utils.module_loading import import_string
from django.views.decorators.http import require_GET

from apps.integrations.mock_product.api import validate_product_endpoint_coverage
from apps.integrations.mock_product.messages import validate_message_catalog
from apps.product_data.catalog import load_product_catalog

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
def readiness(request):
    checks: dict[str, object] = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"

        catalog = load_product_catalog()
        checks["catalog"] = {
            "status": "ok",
            "version": catalog.reference.version,
            "products": len(catalog.products),
        }
        validate_product_endpoint_coverage(set(catalog.products))
        checks["productEndpoints"] = "ok"
        checks["rawMessages"] = {"status": "ok", **validate_message_catalog()}
        if settings.EXTERNAL_SYSTEM_MODE == "real":
            if not settings.APPLICATION_LINK_PROTOCOL_CONFIRMED:
                raise RuntimeError("APPLICATION_LINK_PROTOCOL_CONFIRMED 未确认")
            if not settings.APPLICATION_LINK_SIGNER:
                raise RuntimeError("APPLICATION_LINK_SIGNER 未配置")
            signer = import_string(settings.APPLICATION_LINK_SIGNER)
            if not callable(signer):
                raise RuntimeError("APPLICATION_LINK_SIGNER 不可调用")
            checks["applicationLinkProtocol"] = "ok"
    except Exception as exc:
        logger.exception("readiness_check_failed")
        checks["error"] = type(exc).__name__
        return JsonResponse({"status": "not_ready", "checks": checks}, status=503)
    return JsonResponse({"status": "ready", "checks": checks})


def frontend(request, path: str = ""):
    if not settings.FRONTEND_DIST_DIR:
        raise Http404("Frontend dist directory is not configured")

    dist_dir = Path(settings.FRONTEND_DIST_DIR).resolve()
    requested_path = (dist_dir / path).resolve() if path else dist_dir / "index.html"
    try:
        requested_path.relative_to(dist_dir)
    except ValueError as exc:
        raise Http404("Invalid frontend path") from exc

    if requested_path.is_file():
        content_type = mimetypes.guess_type(str(requested_path))[0]
        return FileResponse(requested_path.open("rb"), content_type=content_type)

    index_path = dist_dir / "index.html"
    if index_path.is_file():
        return FileResponse(index_path.open("rb"), content_type="text/html; charset=utf-8")

    raise Http404("Frontend index.html does not exist")
