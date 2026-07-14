from django.urls import path

from apps.product_data.card_status.views import apply_card_action, card_status_config, search_cards

urlpatterns = [
    path("tools/cards/config", card_status_config, name="card-status-config"),
    path("tools/cards/search", search_cards, name="card-status-search"),
    path(
        "tools/cards/<str:card_no>/actions/<str:action>",
        apply_card_action,
        name="card-status-action",
    ),
]
