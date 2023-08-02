from django.contrib import admin

from .models import TelegramChat, TelegramState, TelegramUser

admin.site.register(TelegramUser)
admin.site.register(TelegramChat)
admin.site.register(TelegramState)

