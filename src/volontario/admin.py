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


# Register your models here.
admin.site.register(Organizzazione)
admin.site.register(TipoVeicolo)
admin.site.register(Veicolo)
admin.site.register(TipoOggetto)
admin.site.register(Oggetto)


@admin.register(Certificazione)
class CertificazioneAdmin(admin.ModelAdmin):
    search_fields = ["nome"]
