import hr.views
from django.urls import path

app_name = "hr"
urlpatterns = [
    path("", hr.views.main, name="home"),
    path("user/<int:id>", hr.views.detail_page, name="userpage"),
    path("link_tg/<uuid:uuid>", hr.views.link_tg, name="link_telegram"),
]
