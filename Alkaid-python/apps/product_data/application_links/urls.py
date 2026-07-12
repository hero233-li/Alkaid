from django.urls import path

from apps.product_data.application_links.views import generate_application_link

urlpatterns = [
    path(
        "tools/application-links/generate",
        generate_application_link,
        name="application-link-generate",
    ),
]
