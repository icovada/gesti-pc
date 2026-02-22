from django.contrib import admin

from magazzino.models import Dotazione

from .models import (
    Certificazione,
    CertificazioneVolontarioMap,
    Oggetto,
    Organizzazione,
    TipoOggetto,
    TipoVeicolo,
    Veicolo,
    Volontario,
)

# Register your models here.


@admin.register(TipoVeicolo)
class TipoVeicoloAdmin(admin.ModelAdmin):
    exclude = ["pkid"]
    search_fields = ["tipo"]


@admin.register(Veicolo)
class VeicoloAdmin(admin.ModelAdmin):
    search_fields = ["targa"]


class VeicoloInline(admin.TabularInline):
    model = Veicolo
    extra = 1
    autocomplete_fields = ["tipo"]


@admin.register(TipoOggetto)
class TipoOggettoAdmin(admin.ModelAdmin):
    exclude = ["pkid"]
    search_fields = ["tipo"]


@admin.register(Oggetto)
class OggettoAdmin(admin.ModelAdmin):
    exclude = ["pkid"]
    search_fields = ["descrizione", "tipo"]


class CertificazioneVolontarioMapInline(admin.TabularInline):
    model = CertificazioneVolontarioMap
    extra = 1
    autocomplete_fields = ["fkcertificazione"]


class DotazioneInline(admin.TabularInline):
    model = Dotazione
    extra = 1
    autocomplete_fields = ["tipo"]
    fields = ["tipo", "taglia", "data_assegnazione", "data_restituzione", "note"]
    verbose_name = "Dotazione assegnata"
    verbose_name_plural = "Dotazioni assegnate"


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
    inlines = [CertificazioneVolontarioMapInline, DotazioneInline]
    autocomplete_fields = ["fkorganizzazione"]
    search_fields = ["nome", "cognome", "codice_fiscale"]
    list_filter = ["fkorganizzazione"]

    def get_fields(self, request, obj=None):
        fields = [
            "codice_fiscale",
            "nome",
            "cognome",
            "fkorganizzazione",
            "data_di_nascita",
            "luogo_di_nascita",
        ]
        # Only superusers can see/edit user link
        if request.user.is_superuser:
            fields.append("user")
        return fields


@admin.register(Certificazione)
class CertificazioneAdmin(admin.ModelAdmin):
    search_fields = ["nome"]
    exclude = ["pkid"]


@admin.register(Organizzazione)
class OrganizzazioneAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    exclude = ["pkid"]
    inlines = [VeicoloInline]
