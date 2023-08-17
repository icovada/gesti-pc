from django.urls import path

from . import views

urlpatterns = [
    path("", views.main, name="warehouse_main"),
    path("item/<int:id>", views.inventory_detail, name="warehouse_item_detail"),
    path("item/<int:id>/edit", views.inventory_detail_edit, name="warehouse_item_detail_edit"),
    path("new", views.inventory_item_create, name="warehouse_item_create"),
]
