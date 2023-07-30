from django.shortcuts import render
from django.db.models import Count, OuterRef, Q, Subquery, Func, F


from .models import Servizio, ServizioResponse

# Create your views here.

def main(request):
    total_response = ServizioResponse.objects.filter(id=OuterRef('id')) \
        .annotate(count=Func(F('id'), function='Count')) \
        .values('count')
    total_acks = ServizioResponse.objects.filter(id=OuterRef('id'), response=1) \
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
    responses = ServizioResponse.objects.filter(fkservizio=id).prefetch_related('fkuser')
    
    return render(request, 'servizio/detail.html', {"curpage": "servizi",
                                                    "servizio": servizio,
                                                    "responses": responses})