from django.urls import path

from apps.product_data.application_data.views import (
    application_data_config,
    generate_application_data,
)

urlpatterns = [
    path("tools/application-data/config", application_data_config, name="application-data-config"),
    path(
        "tools/application-data/generate",
        generate_application_data,
        name="application-data-generate",
    ),
]
