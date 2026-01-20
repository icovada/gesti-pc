from django.contrib import admin

from .models import Servizio, Timbratura, VolontarioServizioMap


@admin.register(Servizio)
class ServizioAdmin(admin.ModelAdmin):
    list_display = ["nome", "date", "volontari_count"]
    list_filter = ["date"]
    search_fields = ["nome"]
    date_hierarchy = "date"

    def volontari_count(self, obj):
        return obj.volontari.count()

    volontari_count.short_description = "Volontari"


@admin.register(VolontarioServizioMap)
class VolontarioServizioMapAdmin(admin.ModelAdmin):
    list_display = ["fkvolontario", "fkservizio", "risposta", "risposta_at"]
    list_filter = ["risposta", "fkservizio"]
    search_fields = ["fkvolontario__nome", "fkvolontario__cognome", "fkservizio__nome"]
    raw_id_fields = ["fkvolontario", "fkservizio"]


@admin.register(Timbratura)
class TimbraturaAdmin(admin.ModelAdmin):
    list_display = ["fkvolontario", "clock_in", "clock_out", "duration_display", "fkservizio"]
    list_filter = ["clock_in", "fkservizio"]
    search_fields = ["fkvolontario__nome", "fkvolontario__cognome"]
    raw_id_fields = ["fkvolontario", "fkservizio"]
    date_hierarchy = "clock_in"

    def duration_display(self, obj):
        if obj.duration is None:
            return "In corso"
        hours = int(obj.duration // 60)
        minutes = int(obj.duration % 60)
        return f"{hours}h {minutes}m"

    duration_display.short_description = "Durata"
