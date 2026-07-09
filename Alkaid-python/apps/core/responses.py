from typing import Any

from django.http import JsonResponse


def api_response(
    data: Any = None,
    *,
    message: str = "",
    status: int = 200,
    ok: bool = True,
) -> JsonResponse:
    return JsonResponse(
        {"ok": ok, "message": message, "data": data},
        status=status,
    )


def api_error(message: str, *, status: int, data: Any = None) -> JsonResponse:
    return api_response(data, message=message, status=status, ok=False)
