from django.contrib import admin

from .models import TelegramUser
from servizio.models import Timbratura


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = [
        "telegram_id",
        "username",
        "first_name",
        "last_name",
        "volontario",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["telegram_id", "username", "first_name", "last_name"]
    raw_id_fields = ["volontario"]
    readonly_fields = ["telegram_id", "chat_id", "created_at", "updated_at"]

    def has_module_permission(self, request):
        """Only show in admin sidebar for superusers or IT Admin group."""
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name="IT Admin").exists()

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)


@admin.register(Timbratura)
class TimbraturaAdmin(admin.ModelAdmin):
    list_display = [
        "fkvolontario",
        "clock_in",
        "clock_out",
        "duration_display",
    ]
    list_filter = ["clock_in", "fkvolontario__fkorganizzazione"]
    search_fields = [
        "fkvolontario__nome",
        "fkvolontario__cognome",
        "fkvolontario__codice_fiscale",
    ]
    raw_id_fields = ["fkvolontario"]
    readonly_fields = ["pkid", "created_at", "duration_display"]
    date_hierarchy = "clock_in"

    @admin.display(description="Durata")
    def duration_display(self, obj):
        if obj.duration is None:
            return "In corso"
        hours = int(obj.duration // 60)
        minutes = int(obj.duration % 60)
        return f"{hours}h {minutes}m"
