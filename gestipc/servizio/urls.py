from django.urls import path

import servizio.views

urlpatterns = [
    path("", servizio.views.main),
]
