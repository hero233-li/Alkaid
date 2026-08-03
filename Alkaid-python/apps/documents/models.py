import uuid

from django.db import models


class DocumentFolder(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["parent", "name"], name="doc_folder_parent_name")]


class StoredDocument(models.Model):
    class Kind(models.TextChoices):
        DOCUMENT = "document", "文档"
        WORD = "word", "在线 Word"
        MULTIDIMENSIONAL_TABLE = "multidimensional-table", "多维表格"
        SPREADSHEET = "spreadsheet", "在线表格"

    class Source(models.TextChoices):
        CREATED = "created", "创建"
        OPENED = "opened", "打开"

    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    content = models.TextField()
    size = models.PositiveBigIntegerField(default=0)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    source = models.CharField(max_length=16, choices=Source.choices)
    folder = models.ForeignKey(
        DocumentFolder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    last_opened_at = models.DateTimeField()

    class Meta:
        ordering = ["-last_opened_at", "-updated_at", "name"]
        indexes = [
            models.Index(fields=["kind", "-updated_at"], name="doc_kind_updated"),
            models.Index(fields=["folder", "name"], name="doc_folder_name"),
        ]


class DocumentAsset(models.Model):
    """Binary resources referenced by document HTML/Markdown instead of base64 data URLs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        StoredDocument,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="assets",
    )
    name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=127)
    size = models.PositiveBigIntegerField()
    content = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["document", "created_at"], name="doc_asset_created")]
