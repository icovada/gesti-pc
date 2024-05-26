from django.contrib import admin

# Register your models here.
from .models import Servizio, ServizioResponse, Timbratura

admin.site.register(Servizio)
admin.site.register(ServizioResponse)
admin.site.register(Timbratura)
