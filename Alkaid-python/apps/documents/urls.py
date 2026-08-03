from django.urls import path

from apps.documents import views

urlpatterns = [
    path("workspace", views.workspace, name="document-workspace"),
    path("items", views.documents, name="document-list-create"),
    path("folders", views.folders, name="document-folder-list-create"),
    path("folders/<str:folder_id>", views.folder_detail, name="document-folder-detail"),
    path("assets", views.upload_asset, name="document-asset-upload"),
    path("assets/<str:asset_id>", views.asset_content, name="document-asset-content"),
    path("import-word", views.import_word, name="document-import-word"),
    path("export-word", views.export_word, name="document-export-word"),
    path("<str:document_id>", views.document_detail, name="document-detail"),
]
