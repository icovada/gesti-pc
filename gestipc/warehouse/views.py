# Create your views here.
from core.forms import UserMultipleChoiceForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http.response import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .forms import InventoryItemEditForm, InventoryItemForm
from .models import InventoryItem, Loan


@login_required
def main(request):
    warehouse_items = InventoryItem.objects.all()
    return render(
        request,
        "warehouse/main.html",
        {"curpage": "warehouse", "warehouse_items": warehouse_items},
    )


@login_required
def inventory_detail(request, id):
    inventory_item = get_object_or_404(InventoryItem, id=id)
    user_queryset = User.objects.all()
    user_form = UserMultipleChoiceForm(user_queryset=user_queryset)
    loans = Loan.objects.filter(fkinventory_item=inventory_item)

    return render(
        request,
        "warehouse/detail.html",
        {
            "curpage": "warehouse",
            "inv_item": inventory_item,
            "user_form": user_form,
            "loans": loans,
        },
    )


@login_required
def inventory_detail_edit(request, id):
    if request.method == "GET":
        inv_item = get_object_or_404(InventoryItem, id=id)
        inv_item_form = InventoryItemEditForm(instance=inv_item)
        inv_item_form.excluded_fields = ["model", "brand"]
        return render(
            request,
            "core/base_with_form.html",
            {"title": "Modifica oggetto", "form": inv_item_form},
        )
    elif request.method == "POST":
        inv_item_form = InventoryItemEditForm(
            request.POST, instance=get_object_or_404(InventoryItem, id=id)
        )
        if inv_item_form.is_valid():
            item = inv_item_form.save()

            return HttpResponseRedirect(
                reverse("warehouse_item_detail", args=[item.id])
            )

    else:
        return HttpResponseNotAllowed


@login_required
def inventory_item_create(request):
    if request.method == "GET":
        inv_item_form = InventoryItemForm()
        return render(
            request,
            "core/base_with_form.html",
            {"title": "Creazione nuovo oggetto in inventario", "form": inv_item_form},
        )
    elif request.method == "POST":
        inv_item_form = InventoryItemForm(request.POST)
        if inv_item_form.is_valid():
            item = inv_item_form.save()

            return HttpResponseRedirect(
                reverse("warehouse_item_detail", args=[item.id])
            )

    else:
        return HttpResponseNotAllowed


@login_required
def inventory_assign(request, id: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    try:
        assert (
            "warehouse.add_loan" in request.user.get_group_permissions()
        ), "L'utente non ha i permessi di assegnare un oggetto"
    except AssertionError as permission_error:
        return HttpResponseForbidden(content=permission_error)

    assignee_id = request.POST["user"]
    assignee_obj = get_object_or_404(User, id=assignee_id)

    thisloan = Loan(
        fkinventory_item=get_object_or_404(InventoryItem, id=id),
        fkuser=assignee_obj,
    )

    thisloan.save()

    return HttpResponseRedirect(
        reverse("warehouse_loan_detail", args=[id, thisloan.id])
    )


@login_required
def loan_detail(request, id: int, loanid: int):
    return HttpResponse("ciao bro")
