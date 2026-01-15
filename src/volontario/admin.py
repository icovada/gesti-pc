from django.contrib import admin
from .models import (
    Organizzazione,
    Volontario,
    TipoVeicolo,
    Veicolo,
    TipoOggetto,
    Oggetto,
    Certificazione,
    CertificazioneVolontarioMap,
)

# Register your models here.
admin.site.register(TipoVeicolo)
admin.site.register(Veicolo)
admin.site.register(TipoOggetto)
admin.site.register(Oggetto)


class CertificazioneVolontarioMapInline(admin.TabularInline):
    model = CertificazioneVolontarioMap
    extra = 1
    autocomplete_fields = ["fkcertificazione"]


@admin.register(Volontario)
class VolontarioAdmin(admin.ModelAdmin):
    list_display = [
        "codice_fiscale",
        "nome",
        "cognome",
        "fkorganizzazione",
        "data_di_nascita",
        "luogo_di_nascita",
    ]
    readonly_fields = ["data_di_nascita", "luogo_di_nascita"]
    inlines = [CertificazioneVolontarioMapInline]
    autocomplete_fields = ["fkorganizzazione"]


@admin.register(Certificazione)
class CertificazioneAdmin(admin.ModelAdmin):
    search_fields = ["nome"]


@admin.register(Organizzazione)
class OrganizzazioneAdmin(admin.ModelAdmin):
    search_fields = ["nome"]
