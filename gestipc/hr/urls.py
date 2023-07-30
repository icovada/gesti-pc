from django.urls import path

import hr.views

urlpatterns = [
    path("", hr.views.main),
    path("user/<int:id>", hr.views.detail_page)
]
