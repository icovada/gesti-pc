from uuid import uuid4

from django.db import models
from django.utils import timezone

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


class TimeEntry(models.Model):
    """Tracks volunteer clock in/out times."""

    pkid = models.UUIDField(primary_key=True, default=uuid4)
    volontario = models.ForeignKey(
        Volontario,
        on_delete=models.CASCADE,
        related_name="time_entries",
    )
    clock_in = models.DateTimeField(default=timezone.now)
    clock_out = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registrazione Ore"
        verbose_name_plural = "Registrazioni Ore"
        ordering = ["-clock_in"]

    def __str__(self) -> str:
        status = "in corso" if self.clock_out is None else "completato"
        return f"{self.volontario} - {self.clock_in:%d/%m/%Y %H:%M} ({status})"

    @property
    def is_open(self) -> bool:
        return self.clock_out is None

    @property
    def duration(self):
        """Returns duration in minutes, or None if still open."""
        if self.clock_out is None:
            return None
        delta = self.clock_out - self.clock_in
        return delta.total_seconds() / 60
