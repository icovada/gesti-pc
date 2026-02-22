from uuid import uuid4

from django.db import models

from volontario.models import Volontario


class TipoDotazione(models.Model):
    pkid = models.UUIDField(default=uuid4, primary_key=True)
    nome = models.CharField(max_length=100)
    descrizione = models.TextField(blank=True)

    class Meta:
        verbose_name = "Tipo Dotazione"
        verbose_name_plural = "Tipi Dotazione"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class Dotazione(models.Model):
    pkid = models.UUIDField(default=uuid4, primary_key=True)
    volontario = models.ForeignKey(
        Volontario,
        on_delete=models.CASCADE,
        related_name="dotazioni",
    )
    tipo = models.ForeignKey(
        TipoDotazione,
        on_delete=models.PROTECT,
        related_name="assegnazioni",
    )
    taglia = models.CharField(max_length=10, blank=True)
    data_assegnazione = models.DateField()
    data_restituzione = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "Dotazione"
        verbose_name_plural = "Dotazioni"
        ordering = ["-data_assegnazione"]

    @property
    def is_attivo(self) -> bool:
        return self.data_restituzione is None

    def __str__(self) -> str:
        stato = "attivo" if self.is_attivo else "restituito"
        taglia_str = f" ({self.taglia})" if self.taglia else ""
        return f"{self.volontario} - {self.tipo}{taglia_str} ({stato})"


class RequisitoServizioType(models.Model):
    pkid = models.UUIDField(default=uuid4, primary_key=True)
    servizio_type = models.ForeignKey(
        "servizio.ServizioType",
        on_delete=models.CASCADE,
        related_name="requisiti_dotazione",
    )
    tipo_dotazione = models.ForeignKey(
        TipoDotazione,
        on_delete=models.CASCADE,
        related_name="servizi_richiesti",
    )

    class Meta:
        verbose_name = "Requisito Dotazione Servizio"
        verbose_name_plural = "Requisiti Dotazione Servizio"
        unique_together = ["servizio_type", "tipo_dotazione"]

    def __str__(self) -> str:
        return f"{self.servizio_type} richiede {self.tipo_dotazione}"


def volontario_ha_dotazioni_per_servizio(volontario, servizio_type) -> bool:
    """Ritorna True se il volontario ha tutte le dotazioni richieste (attive) per il ServizioType."""
    requisiti = RequisitoServizioType.objects.filter(servizio_type=servizio_type)
    if not requisiti.exists():
        return True
    for req in requisiti:
        if not Dotazione.objects.filter(
            volontario=volontario,
            tipo=req.tipo_dotazione,
            data_restituzione__isnull=True,
        ).exists():
            return False
    return True
