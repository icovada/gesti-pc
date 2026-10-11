from django.contrib import admin

from .models import PushSubscription


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("volontario", "user_agent", "created_at", "last_success_at")
    list_select_related = ("volontario",)
    search_fields = ("volontario__nome", "volontario__cognome", "user_agent")
    readonly_fields = ("endpoint", "p256dh", "auth", "user_agent", "created_at")
