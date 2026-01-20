import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from volontario.models import Volontario


def generate_login_token():
    return secrets.token_urlsafe(32)


class LoginToken(models.Model):
    """One-time login token sent via Telegram bot."""

    token = models.CharField(max_length=64, primary_key=True, default=generate_login_token)
    telegram_user = models.ForeignKey(
        "TelegramUser",
        on_delete=models.CASCADE,
        related_name="login_tokens",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Token di Login"
        verbose_name_plural = "Token di Login"

    def __str__(self) -> str:
        status = "usato" if self.used_at else "valido"
        return f"Token per {self.telegram_user} ({status})"

    @property
    def is_valid(self) -> bool:
        """Token is valid if unused and less than 10 minutes old."""
        if self.used_at:
            return False
        expiry = self.created_at + timedelta(minutes=10)
        return timezone.now() < expiry

    def get_login_url(self) -> str:
        """Generate the full login URL."""
        base_url = getattr(settings, "SITE_URL", "http://localhost:8000")
        return f"{base_url}/auth/login/{self.token}/"


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


class WebLoginRequest(models.Model):
    """Tracks web login requests pending approval via Telegram."""

    class Status(models.TextChoices):
        PENDING = "pending", "In attesa"
        APPROVED = "approved", "Approvato"
        DENIED = "denied", "Rifiutato"
        EXPIRED = "expired", "Scaduto"

    token = models.CharField(max_length=64, primary_key=True, default=generate_login_token)
    volontario = models.ForeignKey(
        Volontario,
        on_delete=models.CASCADE,
        related_name="web_login_requests",
    )
    telegram_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name="web_login_requests",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    telegram_message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Richiesta Login Web"
        verbose_name_plural = "Richieste Login Web"

    def __str__(self) -> str:
        return f"Login request for {self.volontario} ({self.get_status_display()})"

    @property
    def is_pending(self) -> bool:
        """Check if request is still pending and not expired."""
        if self.status != self.Status.PENDING:
            return False
        expiry = self.created_at + timedelta(minutes=5)
        return timezone.now() < expiry

    @property
    def is_approved(self) -> bool:
        return self.status == self.Status.APPROVED
