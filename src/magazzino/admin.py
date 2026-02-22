from django.contrib import admin

from .models import Dotazione, RequisitoServizioType, TipoDotazione


class ServizioRichiedenteDotazioneInline(admin.TabularInline):
    model = RequisitoServizioType
    extra = 0
    fields = ["servizio_type"]
    readonly_fields = ["servizio_type"]
    can_delete = False
    verbose_name = "Servizio che richiede questa dotazione"
    verbose_name_plural = "Servizi che richiedono questa dotazione"


@admin.register(TipoDotazione)
class TipoDotazioneAdmin(admin.ModelAdmin):
    exclude = ["pkid"]
    search_fields = ["nome"]
    inlines = [ServizioRichiedenteDotazioneInline]


class IsAttivoFilter(admin.SimpleListFilter):
    title = "stato"
    parameter_name = "attivo"

    def lookups(self, request, model_admin):
        return [
            ("si", "Attivo"),
            ("no", "Restituito"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "si":
            return queryset.filter(data_restituzione__isnull=True)
        if self.value() == "no":
            return queryset.filter(data_restituzione__isnull=False)
        return queryset


@admin.register(Dotazione)
class DotazioneAdmin(admin.ModelAdmin):
    exclude = ["pkid"]
    list_display = [
        "volontario",
        "tipo",
        "taglia",
        "data_assegnazione",
        "data_restituzione",
        "is_attivo_display",
    ]
    list_filter = ["tipo", IsAttivoFilter]
    search_fields = [
        "volontario__nome",
        "volontario__cognome",
        "tipo__nome",
    ]
    autocomplete_fields = ["volontario", "tipo"]
    date_hierarchy = "data_assegnazione"

    @admin.display(description="Attivo", boolean=True)
    def is_attivo_display(self, obj):
        return obj.is_attivo


@admin.register(RequisitoServizioType)
class RequisitoServizioTypeAdmin(admin.ModelAdmin):
    exclude = ["pkid"]
