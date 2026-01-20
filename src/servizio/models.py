from uuid import uuid4
from django.db import models
from django.utils import timezone


from volontario.models import Volontario

# Create your models here.


class VolontarioServizioMap(models.Model):
    pkid = models.UUIDField(default=uuid4, primary_key=True)
    fkvolontario = models.ForeignKey(Volontario, on_delete=models.CASCADE, null=False)
    fkservizio = models.ForeignKey("Servizio", on_delete=models.CASCADE, null=False)


class Servizio(models.Model):
    pkid = models.UUIDField(default=uuid4, primary_key=True)
    date = models.DateField()
    nome = models.CharField(max_length=150)
    volontari = models.ManyToManyField(to=Volontario, through=VolontarioServizioMap)


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
