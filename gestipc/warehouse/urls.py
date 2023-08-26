from django.urls import path

from . import views

app_name = "warehouse"
urlpatterns = [
    path("", views.main, name="home"),
    path("item/<int:id>/", views.inventory_detail, name="item_detail"),
    path("item/<int:id>/assign", views.inventory_assign, name="item_assign"),
    path(
        "item/<int:id>/loan/<int:loanid>/",
        views.loan_detail,
        name="loan_detail",
    ),
    path(
        "item/<int:id>/edit",
        views.inventory_detail_edit,
        name="item_detail_edit",
    ),
    path("new", views.inventory_item_create, name="item_create"),
]
