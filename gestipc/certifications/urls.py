from . import views
from django.urls import path

app_name = "certifications"
urlpatterns = [
    path("", views.main, name="home"),
    path("detail/<int:id>", views.detail_page, name="detail"),
]
