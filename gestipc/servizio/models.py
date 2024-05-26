from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from datetime import datetime as dt

# Create your models here.


class Servizio(models.Model):
    begin_date = models.DateTimeField()
    location = models.CharField(max_length=50)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    poll_id = models.PositiveBigIntegerField(null=True, blank=True)


class ServizioResponse(models.Model):
    class ResponseEnum(models.TextChoices):
        ACCEPTED = "accepted", "Accettato"
        REFUSED = "declined", "Rifiutato"
        MAYBE = "tentative", "Forse"

    fkservizio = models.ForeignKey(Servizio, on_delete=models.CASCADE)
    fkuser = models.ForeignKey(User, on_delete=models.PROTECT)
    response = models.CharField(max_length=10, choices=ResponseEnum.choices)
    last_update = models.DateTimeField(default=timezone.now)


class Timbratura(models.Model):
    fkservizio = models.ForeignKey(Servizio, on_delete=models.CASCADE)
    fkuser = models.ForeignKey(User, on_delete=models.CASCADE)
    datetime_begin = models.DateTimeField(default=dt.now)
    datetime_end = models.DateTimeField(null=True, blank=True)
