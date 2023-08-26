from django.db.models import F, Func, OuterRef, Subquery
from django.shortcuts import redirect, render
from tg_bot.bot import bot
from tg_bot.processors import nuovo_servizio_callback

from .models import Servizio, ServizioResponse

# Create your views here.


def main(request):
    total_response = (
        ServizioResponse.objects.filter(fkservizio=OuterRef("id"))
        .annotate(count=Func(F("id"), function="Count"))
        .values("count")
    )
    total_acks = (
        ServizioResponse.objects.filter(
            fkservizio=OuterRef("id"), response=ServizioResponse.ResponseEnum.ACCEPTED
        )
        .annotate(count=Func(F("id"), function="Count"))
        .values("count")
    )
    servizi = Servizio.objects.order_by("-begin_date").annotate(
        total_response=Subquery(total_response), total_acks=Subquery(total_acks)
    )
    return render(
        request, "servizio/main.html", {"curpage": "servizi", "servizi": servizi}
    )


def detail(request, id):
    servizio = Servizio.objects.get(id=id)
    responses = ServizioResponse.objects.filter(fkservizio=id).prefetch_related(
        "fkuser"
    )

    return render(
        request,
        "servizio/detail.html",
        {"curpage": "servizi", "servizio": servizio, "responses": responses},
    )


def new(request):
    if request.method == "POST":
        servizio = Servizio.objects.create(
            begin_date=f"{request.POST['begin_date']} {request.POST['begin_time']}",
            location=request.POST["location"],
            created_by=request.user,
        )

        poll_id = nuovo_servizio_callback(bot, servizio)

        servizio.poll_id = poll_id
        servizio.save()

        return redirect(main)
    else:
        return render(request, "servizio/new.html", {"curpage": "servizi"})
