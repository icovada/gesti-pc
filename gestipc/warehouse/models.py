from django.db import models
from django.core.validators import MaxValueValidator

# Create your models here.


class InventoryItem(models.Model):
    model = models.CharField(max_length=50, verbose_name="Modello")
    brand = models.CharField(max_length=20, verbose_name="Marca")
    kind = models.CharField(max_length=20, verbose_name="Tipo")
    picture = models.ImageField(verbose_name="Foto", null=True, blank=True)
    conditions = models.PositiveIntegerField(
        verbose_name="Condizioni", default=5, validators=[MaxValueValidator(5)])
    notes = models.TextField(verbose_name="Note aggiuntive")
