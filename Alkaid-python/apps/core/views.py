import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_GET

from apps.core.readiness import collect_readiness
from apps.core.responses import api_response
from apps.integrations.cjdk_jyrc.config import get_cjdk_jyrc_settings

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_GET
def readiness(request):
    report = collect_readiness()
    if not report.ready:
        logger.error(
            "readiness_check_failed",
            exc_info=(
                type(report.error),
                report.error,
                report.error.__traceback__,
            )
            if report.error is not None
            else None,
        )
    return JsonResponse(
        {
            "status": "ready" if report.ready else "not_ready",
            "checks": report.checks,
        },
        status=200 if report.ready else 503,
    )


@require_GET
def capabilities(request):
    """Expose every page in the imported frontend for local development."""
    enabled = {
        "product-application": True,
        "business-access-query": True,
        "application-link-generator": True,
        "verification-approval": True,
        "application-data-generator": True,
        "card-status-processing": True,
        "loan-status-processing": True,
        "high-frequency-transaction": True,
        "workflow-learning": True,
        "workflow": True,
        "jobs": True,
        "batch": True,
        "schedule": True,
        "data": True,
        "workbench": settings.WORKBENCH_ENABLED,
        "settings": True,
    }
    return api_response(
        {
            "externalSystemMode": get_cjdk_jyrc_settings().mode,
            "features": {
                key: {
                    "enabled": value,
                    "reason": "",
                }
                for key, value in enabled.items()
            },
        }
    )


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
