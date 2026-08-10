import base64
import binascii
import mimetypes
import re
from typing import Any

from django.conf import settings
from django.db import models, transaction

from apps.workflow.Documents.models import DocumentAsset, DocumentFolder, StoredDocument
from apps.workflow.Documents.schemas import (
    DocumentSubmission,
    FolderSubmission,
    WorkspaceSubmission,
)


class WorkspaceConflict(ValueError):
    pass


def serialize_folder(folder: DocumentFolder) -> dict[str, Any]:
    return {
        "id": folder.id,
        "name": folder.name,
        "parentId": folder.parent_id,
        "createdAt": folder.created_at.isoformat(),
    }


_ASSET_REFERENCE = re.compile(r"/api/documents/assets/([0-9a-fA-F-]{36})")
_DATA_IMAGE = re.compile(
    r'(?P<prefix>src=["\'])data:(?P<mime>image/[a-zA-Z0-9.+-]+);base64,'
    r'(?P<data>[a-zA-Z0-9+/=\s]+)(?P<suffix>["\'])',
    re.IGNORECASE,
)


def serialize_document(
    document: StoredDocument, *, include_content: bool = False
) -> dict[str, Any]:
    payload = {
        "id": document.id,
        "name": document.name,
        "size": document.size,
        "kind": document.kind,
        "source": document.source,
        "locked": document.locked,
        "folderId": document.folder_id,
        "createdAt": document.created_at.isoformat(),
        "updatedAt": document.updated_at.isoformat(),
        "lastOpenedAt": document.last_opened_at.isoformat(),
    }
    if include_content:
        payload["content"] = document.content
    return payload


def read_workspace() -> dict[str, Any]:
    return {
        "documents": [serialize_document(item) for item in StoredDocument.objects.all()],
        "folders": [serialize_folder(item) for item in DocumentFolder.objects.all()],
    }


def _validate_workspace(submission: WorkspaceSubmission) -> None:
    folder_ids = [folder.id for folder in submission.folders]
    document_ids = [document.id for document in submission.documents]
    normalized_names = [document.name.casefold() for document in submission.documents]
    if len(folder_ids) != len(set(folder_ids)):
        raise WorkspaceConflict("文件夹标识不能重复")
    if len(document_ids) != len(set(document_ids)):
        raise WorkspaceConflict("文件标识不能重复")
    if len(normalized_names) != len(set(normalized_names)):
        raise WorkspaceConflict("文件名称不能重复")
    known_folders = set(folder_ids)
    parents = {folder.id: folder.parentId for folder in submission.folders}
    for folder in submission.folders:
        if folder.parentId == folder.id:
            raise WorkspaceConflict("文件夹不能以自身作为父文件夹")
        if folder.parentId and folder.parentId not in known_folders:
            raise WorkspaceConflict(f"父文件夹不存在：{folder.parentId}")
        visited: set[str] = set()
        current = folder.id
        while current:
            if current in visited:
                raise WorkspaceConflict("文件夹层级不能形成循环")
            visited.add(current)
            current = parents.get(current) or ""
    max_content_bytes = settings.DATA_DOCUMENT_MAX_CONTENT_BYTES
    for document in submission.documents:
        if document.folderId and document.folderId not in known_folders:
            raise WorkspaceConflict(f"文件所属文件夹不存在：{document.folderId}")
        if len(document.content.encode("utf-8")) > max_content_bytes:
            raise WorkspaceConflict(f"文件 {document.name} 超过最大容量 {max_content_bytes} 字节")


def _create_folder_tree(folders: list[FolderSubmission]) -> None:
    pending = {folder.id: folder for folder in folders}
    created: set[str] = set()
    while pending:
        ready = [
            folder
            for folder in pending.values()
            if folder.parentId is None or folder.parentId in created
        ]
        if not ready:
            raise WorkspaceConflict("文件夹层级无法保存")
        DocumentFolder.objects.bulk_create(
            [
                DocumentFolder(
                    id=folder.id,
                    name=folder.name,
                    parent_id=folder.parentId,
                    created_at=folder.createdAt,
                )
                for folder in ready
            ]
        )
        for folder in ready:
            created.add(folder.id)
            pending.pop(folder.id)


@transaction.atomic
def replace_workspace(submission: WorkspaceSubmission) -> dict[str, Any]:
    _validate_workspace(submission)
    StoredDocument.objects.all().delete()
    DocumentFolder.objects.all().delete()
    _create_folder_tree(submission.folders)
    for document in submission.documents:
        create_document(document)
    return read_workspace()


def _validate_document_folder(folder_id: str | None) -> None:
    if folder_id and not DocumentFolder.objects.filter(pk=folder_id).exists():
        raise WorkspaceConflict("文件所属文件夹不存在")


def _validate_content(content: str) -> int:
    content_size = len(content.encode("utf-8"))
    if content_size > settings.DATA_DOCUMENT_MAX_CONTENT_BYTES:
        raise WorkspaceConflict("文件正文超过最大容量；图片请通过资源上传接口保存")
    return content_size


def _externalize_data_images(document: StoredDocument, content: str) -> str:
    def replace(match: re.Match[str]) -> str:
        try:
            encoded = re.sub(r"\s+", "", match.group("data"))
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise WorkspaceConflict("文档中包含无效的 Base64 图片") from exc
        if len(decoded) > settings.DATA_DOCUMENT_MAX_ASSET_BYTES:
            raise WorkspaceConflict("文档中的单张图片超过最大容量")
        content_type = match.group("mime").lower()
        suffix = mimetypes.guess_extension(content_type) or ".bin"
        asset = DocumentAsset.objects.create(
            document=document,
            name=f"embedded-image{suffix}",
            content_type=content_type,
            size=len(decoded),
            content=decoded,
        )
        return (
            f'{match.group("prefix")}/api/documents/assets/{asset.id}'
            f'{match.group("suffix")}'
        )

    return _DATA_IMAGE.sub(replace, content)


def _sync_referenced_assets(document: StoredDocument) -> None:
    referenced_ids = set(_ASSET_REFERENCE.findall(document.content))
    if referenced_ids:
        DocumentAsset.objects.filter(id__in=referenced_ids, document__isnull=True).update(
            document=document
        )
    owned_assets = DocumentAsset.objects.filter(document=document)
    if referenced_ids:
        owned_assets.exclude(id__in=referenced_ids).delete()
    else:
        owned_assets.delete()
    asset_size = document.assets.aggregate(total=models.Sum("size"))["total"] or 0
    document.size = len(document.content.encode("utf-8")) + asset_size
    document.save(update_fields=["size"])


def _save_document_content(document: StoredDocument, content: str) -> None:
    rewritten_content = _externalize_data_images(document, content)
    _validate_content(rewritten_content)
    document.content = rewritten_content
    document.save(update_fields=["content"])
    _sync_referenced_assets(document)


@transaction.atomic
def create_document(submission: DocumentSubmission) -> StoredDocument:
    _validate_document_folder(submission.folderId)
    document = StoredDocument.objects.create(
        id=submission.id,
        name=submission.name,
        content="",
        size=0,
        kind=submission.kind,
        source=submission.source,
        locked=submission.locked,
        folder_id=submission.folderId,
        created_at=submission.createdAt,
        updated_at=submission.updatedAt,
        last_opened_at=submission.lastOpenedAt,
    )
    _save_document_content(document, submission.content)
    return document


@transaction.atomic
def update_document(document: StoredDocument, submission: DocumentSubmission) -> StoredDocument:
    if submission.id != document.id:
        raise WorkspaceConflict("文件标识不能修改")
    _validate_document_folder(submission.folderId)
    document.name = submission.name
    document.kind = submission.kind
    document.source = submission.source
    document.locked = submission.locked
    document.folder_id = submission.folderId
    document.created_at = submission.createdAt
    document.updated_at = submission.updatedAt
    document.last_opened_at = submission.lastOpenedAt
    document.save()
    _save_document_content(document, submission.content)
    return document


@transaction.atomic
def create_folder(submission: FolderSubmission) -> DocumentFolder:
    if submission.parentId and not DocumentFolder.objects.filter(pk=submission.parentId).exists():
        raise WorkspaceConflict("父文件夹不存在")
    return DocumentFolder.objects.create(
        id=submission.id,
        name=submission.name,
        parent_id=submission.parentId,
        created_at=submission.createdAt,
    )


def move_document(document: StoredDocument, folder_id: str | None) -> StoredDocument:
    _validate_document_folder(folder_id)
    document.folder_id = folder_id
    document.save(update_fields=["folder"])
    return document
