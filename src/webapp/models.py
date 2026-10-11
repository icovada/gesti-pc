from django.db import models

from volontario.models import Volontario


class PushSubscription(models.Model):
    """Iscrizione Web Push di un dispositivo (browser o app installata)."""

    volontario = models.ForeignKey(
        Volontario, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_success_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Dispositivo per notifiche"
        verbose_name_plural = "Dispositivi per notifiche"

    def __str__(self) -> str:
        return f"{self.volontario} — {self.user_agent[:60] or self.endpoint[:60]}"

    def as_subscription_info(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.p256dh, "auth": self.auth},
        }
