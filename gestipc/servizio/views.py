from django.shortcuts import render

from .models import Servizio

# Create your views here.

def main(request):
    servizi = Servizio.objects.order_by('begin_date').all()
    return render(request, 'servizio/main.html', {"servizi": servizi})
