from uuid import uuid4
from django.contrib.auth.models import AbstractUser
from django.db import models

from .codicefiscale import CodiceFiscale
# Create your models here.


class CodiceFiscaleField(models.CharField):
    description = "Codice Fiscale"

    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 16
        super().__init__(*args, **kwargs)

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        if value:
            CodiceFiscale(value)


class Organizzazione(models.Model):
    pkid = models.UUIDField(default=uuid4, primary_key=True, null=False)
    name = models.CharField(max_length=30)


class Volontario(AbstractUser):
    codice_fiscale = CodiceFiscaleField(primary_key=True, null=False, blank=False)
    nome = models.CharField(max_length=30)
    cognome = models.CharField(max_length=30)
    fkorganizzazione = models.ForeignKey(Organizzazione, on_delete=models.CASCADE)


class BaseOggetto(models.Model):
    pkid = models.UUIDField(primary_key=True, null=False, default=uuid4)
    fkorganizzazione = models.ForeignKey(Organizzazione, on_delete=models.SET_NULL, null=True)
    descrizione = models.TextField()


class TipoOggetto(models.Model):
    pkid = models.UUIDField(primary_key=True, null=False, default=uuid4)
    tipo = models.CharField(max_length=20)


class Oggetto(BaseOggetto):
    tipo = models.ForeignKey(TipoOggetto, on_delete=models.SET_NULL, null=True)


class TipoVeicolo(models.Model):
    pkid = models.UUIDField(primary_key=True, null=False, default=uuid4)
    tipo = models.CharField(max_length=20)


class Veicolo(BaseOggetto):
    targa = models.CharField(max_length=12)
    tipo = models.ForeignKey(TipoVeicolo, on_delete=models.SET_NULL, null=True)
