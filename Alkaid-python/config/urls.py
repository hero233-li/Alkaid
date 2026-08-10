from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from apps.core.views import capabilities, frontend, health, readiness

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("health/ready/", readiness, name="readiness"),
    path("api/meta/capabilities", capabilities, name="capabilities"),
    path("api/jobs/", include("apps.workflow.Jobs.urls")),
    path("api/documents/", include("apps.workflow.Documents.urls")),
    path("api/portal/", include("apps.workflow.System_menu.urls")),
    path("api/product-data/", include("apps.workflow.application_links.urls")),
    path("api/product-data/", include("apps.workflow.product_applications.urls")),
]

if settings.WORKBENCH_ENABLED:
    urlpatterns.append(path("api/workbench/", include("apps.workflow.Apifox.urls")))

if settings.FRONTEND_DIST_DIR:
    urlpatterns.append(re_path(r"^(?P<path>.*)$", frontend, name="frontend"))
