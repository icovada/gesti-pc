from django.db import models

from volontario.models import Volontario


class TelegramUser(models.Model):
    """Links a Telegram user ID to a Volontario record."""

    telegram_id = models.BigIntegerField(primary_key=True)
    volontario = models.OneToOneField(
        Volontario,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="telegram_user",
    )
    chat_id = models.BigIntegerField()
    username = models.CharField(max_length=32, blank=True, null=True)
    first_name = models.CharField(max_length=64, blank=True, null=True)
    last_name = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Utente Telegram"
        verbose_name_plural = "Utenti Telegram"

    def __str__(self) -> str:
        if self.volontario:
            return f"@{self.username or self.telegram_id} → {self.volontario}"
        return f"@{self.username or self.telegram_id} (non associato)"

    @property
    def is_linked(self) -> bool:
        return self.volontario_id is not None
