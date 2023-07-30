from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# Create your models here.

class Servizio(models.Model):
    begin_date = models.DateTimeField()
    location = models.CharField(max_length=50)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)


class ServizioResponse(models.Model):
    class ResponseEnum(models.IntegerChoices):
        ACCEPTED = 1, 'Accettato'
        REFUSED = 2, 'Rifiutato'
        MAYBE = 3, 'Forse'

    fkservizio = models.ForeignKey(Servizio, on_delete=models.CASCADE)
    fkuser = models.ForeignKey(User, on_delete=models.PROTECT)
    response = models.IntegerField(ResponseEnum)
    last_update = models.DateTimeField(default=timezone.now)