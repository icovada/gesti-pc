from . import views
from django.urls import path

app_name = "certifications"
urlpatterns = [
    path("", views.main, name="home"),
]
