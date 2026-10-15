from django.urls import path

from . import profilo, views

app_name = "webapp"

urlpatterns = [
    path("", views.home, name="home"),
    path("profilo/", profilo.profilo, name="profilo"),
    path("profilo/ore/nuova/", profilo.presenza_nuova, name="presenza_nuova"),
    path(
        "profilo/ore/<uuid:pk>/modifica/",
        profilo.presenza_modifica,
        name="presenza_modifica",
    ),
    path("profilo/<slug:sezione>/", profilo.profilo, name="profilo_sezione"),
    path("report/ore/", views.report_ore, name="report_ore"),
    path("auth/telegram/", views.telegram_auth, name="telegram_auth"),
    path("logout/", views.logout_view, name="logout"),
    path("timbra/", views.timbra, name="timbra"),
    path(
        "servizi/<uuid:pk>/termina/",
        views.termina_servizio_view,
        name="termina_servizio",
    ),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("push/subscribe/", views.push_subscribe, name="push_subscribe"),
    path("push/unsubscribe/", views.push_unsubscribe, name="push_unsubscribe"),
    path("push/test/", views.push_test, name="push_test"),
    path("push/azione/", views.push_action, name="push_action"),
]
