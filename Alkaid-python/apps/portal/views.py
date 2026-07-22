from django.db import IntegrityError
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.portal.models import ReleaseNote
from apps.portal.schemas import MenuKeysSubmission, ReleaseNoteSubmission
from apps.portal.services import (
    HIDDEN_MENUS_KEY,
    HOME_SHORTCUTS_KEY,
    read_menu_keys,
    save_menu_keys,
    serialize_release_note,
)


def _validation_error(exc: ValidationError) -> JsonResponse:
    return api_error(f"系统管理参数无效：{exc}", status=400, code="invalid_submission")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def releases(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return api_response([serialize_release_note(note) for note in ReleaseNote.objects.all()])
    try:
        submission = ReleaseNoteSubmission.model_validate_json(request.body)
        note = ReleaseNote.objects.create(**submission.model_dump())
    except ValidationError as exc:
        return _validation_error(exc)
    except IntegrityError:
        return api_error("版本号已存在", status=409, code="conflict")
    return api_response(serialize_release_note(note), status=201)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def release_detail(request: HttpRequest, release_id: int) -> JsonResponse:
    note = get_object_or_404(ReleaseNote, pk=release_id)
    if request.method == "DELETE":
        note.delete()
        return api_response(None)
    try:
        submission = ReleaseNoteSubmission.model_validate_json(request.body)
        note.version = submission.version
        note.content = submission.content
        note.save(update_fields=["version", "content", "updated_at"])
    except ValidationError as exc:
        return _validation_error(exc)
    except IntegrityError:
        return api_error("版本号已存在", status=409, code="conflict")
    return api_response(serialize_release_note(note))


def _menu_keys(request: HttpRequest, preference_key: str) -> JsonResponse:
    if request.method == "GET":
        return api_response(read_menu_keys(preference_key))
    try:
        submission = MenuKeysSubmission.model_validate_json(request.body)
    except ValidationError as exc:
        return _validation_error(exc)
    return api_response(save_menu_keys(preference_key, submission.menuKeys))


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def home_shortcuts(request: HttpRequest) -> JsonResponse:
    return _menu_keys(request, HOME_SHORTCUTS_KEY)


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def hidden_menus(request: HttpRequest) -> JsonResponse:
    return _menu_keys(request, HIDDEN_MENUS_KEY)
