from django.contrib import admin

from magazzino.models import RequisitoServizioType, volontario_ha_dotazioni_per_servizio

from .models import (
    ChecklistItem,
    ChecklistTemplateItem,
    ScheduledTask,
    Servizio,
    ServizioType,
    Timbratura,
    VolontarioServizioMap,
)


class ChecklistTemplateItemInline(admin.TabularInline):
    model = ChecklistTemplateItem
    extra = 3
    fields = ["descrizione", "ordine"]


class RequisitoServizioTypeInline(admin.TabularInline):
    model = RequisitoServizioType
    extra = 1
    autocomplete_fields = ["tipo_dotazione"]
    verbose_name = "Dotazione richiesta"
    verbose_name_plural = "Dotazioni richieste"


@admin.register(ServizioType)
class ServizioTypeAdmin(admin.ModelAdmin):
    list_display = ["nome"]
    search_fields = ["nome"]
    inlines = [ChecklistTemplateItemInline, RequisitoServizioTypeInline]


@admin.register(Servizio)
class ServizioAdmin(admin.ModelAdmin):
    list_display = ["nome", "type", "data_ora", "send_message", "volontari_count"]
    list_filter = ["type", "data_ora", "send_message"]
    search_fields = ["nome"]
    date_hierarchy = "data_ora"

    def volontari_count(self, obj):
        return obj.volontari.count()

    volontari_count.short_description = "Volontari"


@admin.register(VolontarioServizioMap)
class VolontarioServizioMapAdmin(admin.ModelAdmin):
    list_display = ["fkvolontario", "fkservizio", "risposta", "risposta_at", "idoneo_display"]
    list_filter = ["risposta", "fkservizio"]
    search_fields = ["fkvolontario__nome", "fkvolontario__cognome", "fkservizio__nome"]
    raw_id_fields = ["fkvolontario", "fkservizio"]

    @admin.display(description="Dotazioni idonee", boolean=True)
    def idoneo_display(self, obj):
        if obj.fkservizio.type is None:
            return True
        return volontario_ha_dotazioni_per_servizio(obj.fkvolontario, obj.fkservizio.type)


@admin.register(Timbratura)
class TimbraturaAdmin(admin.ModelAdmin):
    list_display = [
        "fkvolontario",
        "clock_in",
        "clock_out",
        "duration_display",
        "fkservizio",
        "fkscheduled_task",
    ]
    list_filter = ["clock_in", "fkservizio", "fkscheduled_task"]
    search_fields = ["fkvolontario__nome", "fkvolontario__cognome"]
    raw_id_fields = ["fkvolontario", "fkservizio", "fkscheduled_task"]
    date_hierarchy = "clock_in"

    def duration_display(self, obj):
        if obj.duration is None:
            return "In corso"
        hours = int(obj.duration // 60)
        minutes = int(obj.duration % 60)
        return f"{hours}h {minutes}m"

    duration_display.short_description = "Durata"


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0
    fields = ["descrizione", "ordine", "completato", "completato_da", "completato_at"]
    readonly_fields = ["completato", "completato_da", "completato_at"]


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ["nome", "type", "deadline", "completed", "volontari_count"]
    list_filter = ["type", "completed", "deadline"]
    search_fields = ["nome"]
    filter_horizontal = ["volontari"]
    date_hierarchy = "deadline"
    inlines = [ChecklistItemInline]
    readonly_fields = ["completed", "completed_at", "notification_sent"]

    def volontari_count(self, obj):
        return obj.volontari.count()

    volontari_count.short_description = "Volontari"
