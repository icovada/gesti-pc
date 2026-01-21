from django.contrib import admin

from .models import LoginToken, TelegramUser


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
    readonly_fields = ["telegram_id", "created_at", "updated_at"]

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


@admin.register(LoginToken)
class LoginTokenAdmin(admin.ModelAdmin):
    list_display = ["token", "telegram_user", "created_at", "used_at", "is_valid"]
    list_filter = ["created_at", "used_at"]
    search_fields = ["token", "telegram_user__username", "telegram_user__telegram_id"]
    raw_id_fields = ["telegram_user"]
    readonly_fields = ["token", "telegram_user", "created_at", "used_at"]

    def has_module_permission(self, request):
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
        return False
