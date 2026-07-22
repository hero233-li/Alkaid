from django.urls import path

from apps.portal import views

urlpatterns = [
    path("releases", views.releases, name="portal-releases"),
    path("releases/<int:release_id>", views.release_detail, name="portal-release-detail"),
    path("home-shortcuts", views.home_shortcuts, name="portal-home-shortcuts"),
    path("hidden-menus", views.hidden_menus, name="portal-hidden-menus"),
]
