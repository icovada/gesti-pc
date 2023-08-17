from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http.response import HttpResponseNotAllowed, HttpResponseRedirect, HttpResponse
from django.contrib.auth.decorators import login_required

# Create your views here.
from .models import InventoryItem
from .forms import InventoryItemForm


@login_required
def main(request):
    warehouse_items = InventoryItem.objects.all()
    return render(request, 'warehouse/main.html', {"curpage": "warehouse",
                                                   "warehouse_items": warehouse_items})

@login_required
def inventory_detail(request, id):
    inventory_item = get_object_or_404(InventoryItem, id=id)
    return render(request, 'warehouse/detail.html', {"curpage": "warehouse",
                                                     "inv_item": inventory_item})

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