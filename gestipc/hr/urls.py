from django.urls import path

import hr.views

urlpatterns = [
    path("", hr.views.main),
]
