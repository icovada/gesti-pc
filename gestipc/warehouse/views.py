from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.
from .models import InventoryItem


@login_required
def main(request):
    warehouse_items = InventoryItem.objects.all()
    return render(request, 'warehouse/main.html', {"curpage": "warehouse",
                                                   "warehouse_items": warehouse_items})
