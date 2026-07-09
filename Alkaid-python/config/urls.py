from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from apps.core.views import frontend, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/jobs/", include("apps.jobs.urls")),
    path("api/product-data/", include("apps.product_data.urls")),
    path("api/workflows/", include("apps.workflows.urls")),
]

if settings.FRONTEND_DIST_DIR:
    urlpatterns.append(re_path(r"^(?P<path>.*)$", frontend, name="frontend"))
