from django.urls import path

from apps.workflow.Apifox import views

urlpatterns = [
    path("execute", views.execute, name="Apifox-execute"),
    path("execute-multipart", views.execute_multipart, name="Apifox-execute-multipart"),
    path("history", views.history, name="Apifox-history"),
    path("history/<int:history_id>", views.history_detail, name="Apifox-history-detail"),
    path("history/<int:history_id>/rename", views.rename_history, name="Apifox-history-rename"),
    path("packages", views.packages, name="Apifox-packages"),
    path("packages/import-saz", views.import_saz, name="Apifox-import-saz"),
    path("packages/<int:package_id>", views.package_detail, name="Apifox-package-detail"),
    path(
        "packages/<int:package_id>/requests/<int:request_id>",
        views.package_request_detail,
        name="Apifox-package-request-detail",
    ),
]
