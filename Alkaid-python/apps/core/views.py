import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})


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
