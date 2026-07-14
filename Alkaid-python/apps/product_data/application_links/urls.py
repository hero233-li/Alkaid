from django.urls import path

from apps.product_data.application_links.views import (
    application_link_config,
    generate_application_link,
)

urlpatterns = [
    path(
        "tools/application-links/config",
        application_link_config,
        name="application-link-config",
    ),
    path(
        "tools/application-links/generate",
        generate_application_link,
        name="application-link-generate",
    ),
]
