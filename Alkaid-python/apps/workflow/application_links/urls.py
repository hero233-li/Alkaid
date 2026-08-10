from django.urls import path

from .api import application_link_config, create_application_link

urlpatterns = [
    path("tools/application-links/config", application_link_config, name="application-link-config"),
    path(
        "tools/application-links/generate",
        create_application_link,
        name="application-link-generate",
    ),
]
