# -*- coding: utf-8 -*-
from django.apps import AppConfig


class TelegramBotHandler(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "tg_bot"

    def ready(self):
        from . import signals
