from django.urls import path

from apps.workbench import views

urlpatterns = [
    path("execute", views.execute, name="workbench-execute"),
    path("execute-multipart", views.execute_multipart, name="workbench-execute-multipart"),
    path("history", views.history, name="workbench-history"),
    path("history/<int:history_id>", views.history_detail, name="workbench-history-detail"),
    path("history/<int:history_id>/rename", views.rename_history, name="workbench-history-rename"),
    path("packages", views.packages, name="workbench-packages"),
    path("packages/import-saz", views.import_saz, name="workbench-import-saz"),
    path("packages/<int:package_id>", views.package_detail, name="workbench-package-detail"),
    path(
        "packages/<int:package_id>/requests/<int:request_id>",
        views.package_request_detail,
        name="workbench-package-request-detail",
    ),
]
