from django.contrib import admin

# Register your models here.
from .models import Servizio, ServizioResponse

admin.site.register(Servizio)
admin.site.register(ServizioResponse)
