from django.urls import path

import hr.views

urlpatterns = [
    path("", hr.views.main),
    path("user/<int:id>", hr.views.detail_page),
    path("link_tg/<uuid:uuid>", hr.views.link_tg)
]
