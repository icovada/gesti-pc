from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# Create your models here.

class Servizio(models.Model):
    begin_date = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)


class ServizioRepsonse(models.Model):
    class ServizioStates(models.IntegerChoices):
        ACCEPTED = 1, 'Accettato'
        REFUSED = 2, 'Rifiutato'
        MAYBE = 3, 'Forse'

    fkservizio = models.ForeignKey(Servizio, on_delete=models.CASCADE)
    fkuser = models.ForeignKey(User, on_delete=models.PROTECT)
    response = ServizioStates
    last_update = models.DateTimeField(default=timezone.now)