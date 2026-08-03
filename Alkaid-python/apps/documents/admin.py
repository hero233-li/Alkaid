from django.contrib import admin

from apps.documents.models import DocumentAsset, DocumentFolder, StoredDocument


@admin.register(DocumentFolder)
class DocumentFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "created_at")
    search_fields = ("name",)


@admin.register(StoredDocument)
class StoredDocumentAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "source", "folder", "size", "updated_at")
    list_filter = ("kind", "source")
    search_fields = ("name", "content")


@admin.register(DocumentAsset)
class DocumentAssetAdmin(admin.ModelAdmin):
    list_display = ("name", "content_type", "size", "document", "created_at")
    search_fields = ("name", "document__name")
