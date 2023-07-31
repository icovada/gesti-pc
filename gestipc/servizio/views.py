from django.shortcuts import render, redirect
from django.db.models import OuterRef, Subquery, Func, F
from .models import Servizio, ServizioResponse

from pcroncellobot.processors import nuovo_servizio_callback
from pcroncellobot.bot import bot

# Create your views here.


def main(request):
    total_response = ServizioResponse.objects.filter(id=OuterRef('id')) \
        .annotate(count=Func(F('id'), function='Count')) \
        .values('count')
    total_acks = ServizioResponse.objects.filter(id=OuterRef('id'), response=ServizioResponse.ResponseEnum.ACCEPTED) \
        .annotate(count=Func(F('id'), function='Count')) \
        .values('count')
    servizi = Servizio.objects.order_by('-begin_date') \
        .annotate(total_response=Subquery(total_response),
                  total_acks=Subquery(total_acks)
                  )
    return render(request, 'servizio/main.html', {"curpage": "servizi",
                                                  "servizi": servizi})


def detail(request, id):
    servizio = Servizio.objects.get(id=id)
    responses = ServizioResponse.objects.filter(
        fkservizio=id).prefetch_related('fkuser')

    return render(request, 'servizio/detail.html', {"curpage": "servizi",
                                                    "servizio": servizio,
                                                    "responses": responses})


def new(request):
    if request.method == 'POST':
        Servizio.objects.create(
            begin_date=f"{request.POST['begin_date']} {request.POST['begin_time']}",
            location=request.POST['location'],
            created_by=request.user,
        )

        nuovo_servizio_callback(bot)

        return redirect(main)
    else:
        return render(request, 'servizio/new.html', {"curpage": "servizi"})