from django.urls import path

from apps.product_applications.api import (
    create_product_application,
    product_application_config,
)

urlpatterns = [
    path("applications/config", product_application_config, name="product-application-config"),
    path("applications", create_product_application, name="product-application-create"),
]
