from django.urls import path

from apps.product_data.business_access.views import (
    business_access_config,
    invalidate_business_access,
    push_business_access_notification,
    query_business_access_notifications,
    search_business_access,
)

urlpatterns = [
    path("business-access/config", business_access_config, name="business-access-config"),
    path("business-access/search", search_business_access, name="business-access-search"),
    path(
        "business-access/<int:record_id>/invalidate",
        invalidate_business_access,
        name="business-access-invalidate",
    ),
    path(
        "business-access/<int:record_id>/notifications/query",
        query_business_access_notifications,
        name="business-access-notifications",
    ),
    path(
        "business-access/<int:record_id>/notifications/<int:notification_id>/<str:action>",
        push_business_access_notification,
        name="business-access-notification-push",
    ),
]
