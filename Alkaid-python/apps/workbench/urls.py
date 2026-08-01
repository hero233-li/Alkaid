from django.urls import path

from apps.workbench import views

urlpatterns = [
    path("execute", views.execute, name="workbench-execute"),
    path("execute-multipart", views.execute_multipart, name="workbench-execute-multipart"),
    path("history", views.history, name="workbench-history"),
    path("history/<int:history_id>", views.history_detail, name="workbench-history-detail"),
    path("history/<int:history_id>/rename", views.rename_history, name="workbench-history-rename"),
]
