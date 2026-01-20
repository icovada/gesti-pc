from uuid import uuid4
from django.db import models
from django.utils import timezone


from volontario.models import Volontario

# Create your models here.


class VolontarioServizioMap(models.Model):
    class Risposta(models.TextChoices):
        SI = "si", "Sì"
        NO = "no", "No"
        FORSE = "forse", "Forse"

    pkid = models.UUIDField(default=uuid4, primary_key=True)
    fkvolontario = models.ForeignKey(Volontario, on_delete=models.CASCADE, null=False)
    fkservizio = models.ForeignKey("Servizio", on_delete=models.CASCADE, null=False)
    risposta = models.CharField(max_length=10, choices=Risposta.choices, null=True, blank=True)
    risposta_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["fkvolontario", "fkservizio"]
        verbose_name = "Disponibilità Volontario"
        verbose_name_plural = "Disponibilità Volontari"

    def __str__(self) -> str:
        risposta_display = self.get_risposta_display() if self.risposta else "In attesa"
        return f"{self.fkvolontario} - {self.fkservizio.nome} ({risposta_display})"


class Servizio(models.Model):
    pkid = models.UUIDField(default=uuid4, primary_key=True)
    data_ora = models.DateTimeField()
    nome = models.CharField(max_length=150)
    volontari = models.ManyToManyField(to=Volontario, through=VolontarioServizioMap)
    poll_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    poll_message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Servizio"
        verbose_name_plural = "Servizi"

    def __str__(self) -> str:
        return f"{self.nome} - {self.data_ora:%d/%m/%Y %H:%M}"


class Timbratura(models.Model):
    """Tracks volunteer clock in/out times."""

    pkid = models.UUIDField(primary_key=True, default=uuid4)
    fkvolontario = models.ForeignKey(
        Volontario,
        on_delete=models.CASCADE,
        related_name="time_entries",
    )
    clock_in = models.DateTimeField(default=timezone.now)
    clock_out = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    fkservizio = models.ForeignKey(Servizio, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        verbose_name = "Registrazione Ore"
        verbose_name_plural = "Registrazioni Ore"
        ordering = ["-clock_in"]

    def __str__(self) -> str:
        status = "in corso" if self.clock_out is None else "completato"
        return f"{self.fkvolontario} - {self.clock_in:%d/%m/%Y %H:%M} ({status})"

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
