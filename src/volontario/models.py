from uuid import uuid4
from django.db import models
from django.contrib import admin
from django.forms import ValidationError

from .codicefiscale import CodiceFiscale
# Create your models here.


class CodiceFiscaleField(models.CharField):
    description = "Codice Fiscale"

    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 16
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        """Convert input value to Python object (for forms/deserialization)"""
        if isinstance(value, CodiceFiscale):
            return value

        try:
            return CodiceFiscale(value)
        except Exception as e:
            raise ValidationError() from e

    def from_db_value(self, value, *args):
        """Convert database value to Python object (called when loading from DB)"""
        if value is None:
            return value
        return CodiceFiscale(value)

    def get_prep_value(self, value):
        """Convert Python object to database value"""
        if value is None:
            return value
        if isinstance(value, CodiceFiscale):
            return value.cf  # or value.code if that's the attribute
        return value


class Organizzazione(models.Model):
    pkid = models.UUIDField(default=uuid4, primary_key=True, null=False)
    name = models.CharField(max_length=30)

    def __str__(self) -> str:
        return self.name


class Volontario(models.Model):
    codice_fiscale = CodiceFiscaleField(primary_key=True, null=False, blank=False)
    nome = models.CharField(max_length=30)
    cognome = models.CharField(max_length=30)
    fkorganizzazione = models.ForeignKey(
        Organizzazione, on_delete=models.SET_NULL, blank=False, null=True
    )

    def __str__(self) -> str:
        return f"{self.nome} {self.cognome} - {self.fkorganizzazione if self.fkorganizzazione else ''}"

    @admin.display(description="Data di nascita")
    def data_di_nascita(self):
        from django.utils import formats

        cf: CodiceFiscale = self.codice_fiscale  # type: ignore
        return formats.date_format(cf.birth_date, "d F Y")

    @admin.display(description="Luogo di nascita")
    def luogo_di_nascita(self):
        cf: CodiceFiscale = self.codice_fiscale  # type: ignore
        return f"{cf.birth_place}, {cf.birth_province}"


class TipoOggetto(models.Model):
    pkid = models.UUIDField(primary_key=True, null=False, default=uuid4)
    tipo = models.CharField(max_length=20)

    def __str__(self) -> str:
        return self.tipo


class Oggetto(models.Model):
    pkid = models.UUIDField(primary_key=True, null=False, default=uuid4)
    fkorganizzazione = models.ForeignKey(
        Organizzazione, on_delete=models.SET_NULL, null=True
    )
    descrizione = models.TextField(blank=True)
    tipo = models.ForeignKey(TipoOggetto, on_delete=models.PROTECT, null=False)

    def __str__(self) -> str:
        return f"{self.descrizione} - {self.fkorganizzazione}"


class TipoVeicolo(models.Model):
    pkid = models.UUIDField(primary_key=True, null=False, default=uuid4)
    tipo = models.CharField(max_length=20)

    def __str__(self) -> str:
        return self.tipo


class Veicolo(models.Model):
    targa = models.CharField(max_length=12, primary_key=True)
    fkorganizzazione = models.ForeignKey(
        Organizzazione, on_delete=models.SET_NULL, null=True
    )
    descrizione = models.TextField(blank=True)
    tipo = models.ForeignKey(TipoVeicolo, on_delete=models.PROTECT, null=False)

    def __str__(self) -> str:
        return self.targa


class CertificazioneVolontarioMap(models.Model):
    data_conseguimento = models.DateField()
    fkcertificazione = models.ForeignKey("Certificazione", on_delete=models.CASCADE)
    fkvolontario = models.ForeignKey(Volontario, on_delete=models.CASCADE)


class Certificazione(models.Model):
    pkid = models.UUIDField(primary_key=True, null=False, default=uuid4)
    nome = models.CharField(max_length=50)
    volontari = models.ManyToManyField(to=Volontario, through=CertificazioneVolontarioMap)
