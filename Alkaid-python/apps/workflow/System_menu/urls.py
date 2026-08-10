from django.urls import path

from apps.workflow.System_menu import views

urlpatterns = [
    path("releases", views.releases, name="System_menu-releases"),
    path("releases/<int:release_id>", views.release_detail, name="System_menu-release-detail"),
    path("home-shortcuts", views.home_shortcuts, name="System_menu-home-shortcuts"),
    path("hidden-menus", views.hidden_menus, name="System_menu-hidden-menus"),
    path(
        "auto-expanded-menus",
        views.auto_expanded_menus,
        name="System_menu-auto-expanded-menus",
    ),
]
