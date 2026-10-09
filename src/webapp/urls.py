from django.urls import path

from . import views

app_name = "webapp"

urlpatterns = [
    path("", views.home, name="home"),
    path("report/ore/", views.report_ore, name="report_ore"),
    path("auth/telegram/", views.telegram_auth, name="telegram_auth"),
    path("logout/", views.logout_view, name="logout"),
]
