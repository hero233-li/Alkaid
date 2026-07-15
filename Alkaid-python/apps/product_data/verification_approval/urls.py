from django.urls import path

from apps.product_data.verification_approval.views import (
    claim_verification,
    refresh_verification,
    return_verification,
    search_verification,
    submit_verification_action,
    update_verification_item_status,
    verification_config,
)

urlpatterns = [
    path(
        "verification-approval/config",
        verification_config,
        name="verification-approval-config",
    ),
    path(
        "verification-approval/search",
        search_verification,
        name="verification-approval-search",
    ),
    path(
        "verification-approval/<str:task_id>/claim",
        claim_verification,
        name="verification-approval-claim",
    ),
    path(
        "verification-approval/<str:task_id>/return",
        return_verification,
        name="verification-approval-return",
    ),
    path(
        "verification-approval/<str:task_id>/refresh",
        refresh_verification,
        name="verification-approval-refresh",
    ),
    path(
        "verification-approval/<str:task_id>/items/<str:item_id>",
        update_verification_item_status,
        name="verification-approval-item-update",
    ),
    path(
        "verification-approval/<str:task_id>/actions/<str:action>",
        submit_verification_action,
        name="verification-approval-action",
    ),
]
