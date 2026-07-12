from django.urls import include, path

urlpatterns = [
    path("", include("apps.product_data.product_applications.urls")),
    path("", include("apps.product_data.application_links.urls")),
    path("", include("apps.product_data.business_access.urls")),
    path("", include("apps.product_data.verification_approval.urls")),
]
