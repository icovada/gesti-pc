from django.apps import AppConfig


class WebappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "webapp"
    verbose_name = "Web App"

    def ready(self):
        from . import signals  # noqa: F401
