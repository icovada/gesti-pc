from django.urls import path

import servizio.views

urlpatterns = [
    path("", servizio.views.main),
    path("<int:id>", servizio.views.detail),
    path("new", servizio.views.new)
]
