from django.apps import AppConfig


class ServizioConfig(AppConfig):
    name = "servizio"

    def ready(self):
        import servizio.signals  # noqa: F401
