from django.urls import path

from . import views

app_name = "webapp"

urlpatterns = [
    path("", views.home, name="home"),
    path("report/ore/", views.report_ore, name="report_ore"),
    path("auth/telegram/", views.telegram_auth, name="telegram_auth"),
    path("logout/", views.logout_view, name="logout"),
    path("timbra/", views.timbra, name="timbra"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("push/subscribe/", views.push_subscribe, name="push_subscribe"),
    path("push/unsubscribe/", views.push_unsubscribe, name="push_unsubscribe"),
    path("push/test/", views.push_test, name="push_test"),
    path("push/azione/", views.push_action, name="push_action"),
]
