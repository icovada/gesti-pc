import servizio.views
from django.urls import path

app_name = "servizio"
urlpatterns = [
    path("", servizio.views.main, name="home"),
    path("<int:id>", servizio.views.detail, name="detail"),
    path("new", servizio.views.new, name="new"),
]
