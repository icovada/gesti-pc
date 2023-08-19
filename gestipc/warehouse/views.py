from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from django.http.response import HttpResponseNotAllowed, HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import login_required

# Create your views here.
from core.forms import UserMultipleChoiceForm
from .models import InventoryItem
from .forms import InventoryItemForm, InventoryItemEditForm


@login_required
def main(request):
    warehouse_items = InventoryItem.objects.all()
    return render(request, 'warehouse/main.html', {"curpage": "warehouse",
                                                   "warehouse_items": warehouse_items})


@login_required
def inventory_detail(request, id):
    inventory_item = get_object_or_404(InventoryItem, id=id)
    user_queryset = User.objects.all()
    user_form = UserMultipleChoiceForm(user_queryset=user_queryset)

    return render(request, 'warehouse/detail.html', {"curpage": "warehouse",
                                                     "inv_item": inventory_item,
                                                     "user_form": user_form})


@login_required
def inventory_detail_edit(request, id):
    if request.method == "GET":
        inv_item = get_object_or_404(InventoryItem, id=id)
        inv_item_form = InventoryItemEditForm(instance=inv_item)
        inv_item_form.excluded_fields = ["model", "brand"]
        return render(request, 'core/base_with_form.html', {"title": "Modifica oggetto",
                                                            "form": inv_item_form})
    elif request.method == "POST":
        inv_item_form = InventoryItemEditForm(
            request.POST, instance=get_object_or_404(InventoryItem, id=id))
        if inv_item_form.is_valid():
            item = inv_item_form.save()

            return HttpResponseRedirect(reverse("warehouse_item_detail", args=[item.id]))

    else:
        return HttpResponseNotAllowed


@login_required
def inventory_item_create(request):
    if request.method == "GET":
        inv_item_form = InventoryItemForm()
        return render(request, 'core/base_with_form.html', {"title": "Creazione nuovo oggetto in inventario",
                                                            "form": inv_item_form})
    elif request.method == "POST":
        inv_item_form = InventoryItemForm(request.POST)
        if inv_item_form.is_valid():
            item = inv_item_form.save()

            return HttpResponseRedirect(reverse("warehouse_item_detail", args=[item.id]))

    else:
        return HttpResponseNotAllowed
