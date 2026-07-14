from django.urls import path

from apps.product_data.loan_status.views import apply_loan_action, loan_status_config, search_loans

urlpatterns = [
    path("tools/loans/config", loan_status_config, name="loan-status-config"),
    path("tools/loans/search", search_loans, name="loan-status-search"),
    path(
        "tools/loans/<str:contract_no>/actions/<str:action>",
        apply_loan_action,
        name="loan-status-action",
    ),
]
