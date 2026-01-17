from django.contrib import admin

from .models import TelegramUser


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
