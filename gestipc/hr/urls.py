import hr.views
from django.urls import path

app_name = "hr"
urlpatterns = [
    path("", hr.views.main, name="home"),
    path("user/<int:id>", hr.views.detail_page, name="userpage"),
]
