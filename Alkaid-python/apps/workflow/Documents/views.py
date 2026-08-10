import json
from urllib.parse import quote

from django.conf import settings
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError

from apps.core.responses import api_error, api_response
from apps.workflow.Documents.models import DocumentAsset, DocumentFolder, StoredDocument
from apps.workflow.Documents.schemas import (
    DocumentPatchSubmission,
    DocumentSubmission,
    FolderPatchSubmission,
    FolderSubmission,
    WorkspaceSubmission,
)
from apps.workflow.Documents.services import (
    WorkspaceConflict,
    create_document,
    create_folder,
    move_document,
    read_workspace,
    replace_workspace,
    serialize_document,
    serialize_folder,
    update_document,
)
from apps.workflow.Documents.word_import import (
    WordImportError,
    convert_html_to_docx,
    convert_legacy_word_to_html,
)


def _invalid_submission(exc: Exception) -> JsonResponse:
    return api_error(f"文档存储参数无效：{exc}", status=400, code="invalid_submission")


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def workspace(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return api_response(read_workspace())
    if StoredDocument.objects.filter(locked=True).exists():
        return api_error(
            "工作区包含已锁定文件，请先解锁",
            status=409,
            code="document_locked",
        )
    try:
        submission = WorkspaceSubmission.model_validate_json(request.body)
        return api_response(replace_workspace(submission))
    except (ValidationError, WorkspaceConflict) as exc:
        return _invalid_submission(exc)
    except IntegrityError:
        return api_error("文件或文件夹数据冲突", status=409, code="conflict")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def documents(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return api_response([serialize_document(item) for item in StoredDocument.objects.all()])
    try:
        submission = DocumentSubmission.model_validate_json(request.body)
        return api_response(serialize_document(create_document(submission), include_content=True))
    except (ValidationError, WorkspaceConflict) as exc:
        return _invalid_submission(exc)
    except IntegrityError:
        return api_error("文件名称或标识已存在", status=409, code="conflict")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def folders(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return api_response([serialize_folder(item) for item in DocumentFolder.objects.all()])
    try:
        submission = FolderSubmission.model_validate_json(request.body)
        return api_response(serialize_folder(create_folder(submission)))
    except (ValidationError, WorkspaceConflict) as exc:
        return _invalid_submission(exc)
    except IntegrityError:
        return api_error("文件夹标识已存在", status=409, code="conflict")


@csrf_exempt
@require_http_methods(["POST"])
def import_word(request: HttpRequest) -> JsonResponse:
    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return api_error("请选择 Word 文件", status=400, code="missing_file")
    try:
        return api_response(
            {
                "name": uploaded_file.name,
                "html": convert_legacy_word_to_html(uploaded_file),
            }
        )
    except WordImportError as exc:
        return api_error(str(exc), status=400, code="word_import_failed")


@csrf_exempt
@require_http_methods(["POST"])
def export_word(request: HttpRequest) -> HttpResponse:
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return api_error("Word 导出参数无效", status=400, code="invalid_submission")
    html = payload.get("html") if isinstance(payload, dict) else None
    name = payload.get("name") if isinstance(payload, dict) else None
    if not isinstance(html, str) or not html.strip():
        return api_error("Word 内容不能为空", status=400, code="invalid_submission")
    safe_name = str(name or "未命名在线 Word").rsplit(".", 1)[0].strip() or "未命名在线 Word"
    try:
        response = HttpResponse(
            convert_html_to_docx(html),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except WordImportError as exc:
        return api_error(str(exc), status=400, code="word_export_failed")
    encoded_name = quote(f"{safe_name}.docx")
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_name}"
    return response


@csrf_exempt
@require_http_methods(["GET", "PUT", "PATCH", "DELETE"])
def document_detail(request: HttpRequest, document_id: str) -> JsonResponse:
    document = get_object_or_404(StoredDocument, pk=document_id)
    if request.method == "GET":
        return api_response(serialize_document(document, include_content=True))
    if request.method == "DELETE":
        if document.locked:
            return api_error("文件已锁定，请先解锁", status=409, code="document_locked")
        document.delete()
        return api_response(None)
    if request.method == "PATCH":
        try:
            submission = DocumentPatchSubmission.model_validate_json(request.body)
            fields = submission.model_fields_set
            if document.locked and "folderId" in fields:
                return api_error("文件已锁定，请先解锁", status=409, code="document_locked")
            if "locked" in fields and submission.locked is not None:
                document.locked = submission.locked
                document.save(update_fields=["locked"])
            if "folderId" in submission.model_fields_set:
                move_document(document, submission.folderId)
            if submission.lastOpenedAt is not None:
                document.last_opened_at = submission.lastOpenedAt
                document.save(update_fields=["last_opened_at"])
            return api_response(serialize_document(document))
        except (ValidationError, WorkspaceConflict) as exc:
            return _invalid_submission(exc)
    if document.locked:
        return api_error("文件已锁定，请先解锁", status=409, code="document_locked")
    try:
        submission = DocumentSubmission.model_validate_json(request.body)
        return api_response(
            serialize_document(update_document(document, submission), include_content=True)
        )
    except (ValidationError, WorkspaceConflict) as exc:
        return _invalid_submission(exc)
    except IntegrityError:
        return api_error("文件名称已存在", status=409, code="conflict")


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def folder_detail(request: HttpRequest, folder_id: str) -> JsonResponse:
    folder = get_object_or_404(DocumentFolder, pk=folder_id)
    if request.method == "DELETE":
        descendant_ids = {folder.id}
        pending_ids = {folder.id}
        while pending_ids:
            children = set(
                DocumentFolder.objects.filter(parent_id__in=pending_ids).values_list(
                    "id", flat=True
                )
            )
            pending_ids = children - descendant_ids
            descendant_ids.update(children)
        if StoredDocument.objects.filter(folder_id__in=descendant_ids, locked=True).exists():
            return api_error(
                "文件夹中包含已锁定文件，请先解锁",
                status=409,
                code="document_locked",
            )
        folder.delete()
        return api_response(None)
    try:
        submission = FolderPatchSubmission.model_validate_json(request.body)
        if submission.name is not None:
            folder.name = submission.name
        if "parentId" in submission.model_fields_set:
            if submission.parentId == folder.id:
                raise WorkspaceConflict("文件夹不能以自身作为父文件夹")
            if submission.parentId and not DocumentFolder.objects.filter(
                pk=submission.parentId
            ).exists():
                raise WorkspaceConflict("父文件夹不存在")
            folder.parent_id = submission.parentId
        folder.save()
        return api_response(serialize_folder(folder))
    except (ValidationError, WorkspaceConflict) as exc:
        return _invalid_submission(exc)


@csrf_exempt
@require_http_methods(["POST"])
def upload_asset(request: HttpRequest) -> JsonResponse:
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return api_error("请选择图片", status=400, code="missing_file")
    if uploaded.size > settings.DATA_DOCUMENT_MAX_ASSET_BYTES:
        return api_error("单张图片超过最大容量", status=413, code="asset_too_large")
    content_type = uploaded.content_type or "application/octet-stream"
    if not content_type.startswith("image/"):
        return api_error("资源接口仅支持图片", status=400, code="invalid_asset")
    document_id = request.POST.get("documentId") or None
    document = None
    if document_id:
        document = get_object_or_404(StoredDocument, pk=document_id)
    asset = DocumentAsset.objects.create(
        document=document,
        name=uploaded.name[:255],
        content_type=content_type[:127],
        size=uploaded.size,
        content=b"".join(uploaded.chunks()),
    )
    return api_response(
        {
            "id": str(asset.id),
            "name": asset.name,
            "size": asset.size,
            "contentType": asset.content_type,
            "url": f"/api/documents/assets/{asset.id}",
        }
    )


@require_http_methods(["GET"])
def asset_content(request: HttpRequest, asset_id: str) -> HttpResponse:
    asset = get_object_or_404(DocumentAsset, pk=asset_id)
    response = HttpResponse(bytes(asset.content), content_type=asset.content_type)
    response["Content-Length"] = str(asset.size)
    response["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(asset.name)}"
    response["Cache-Control"] = "private, max-age=31536000, immutable"
    return response
