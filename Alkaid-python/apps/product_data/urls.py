from django.urls import include, path

urlpatterns = [
    path("", include("apps.product_data.product_applications.urls")),
]
