from django.db import models
from django.core.validators import MaxValueValidator
from django.contrib.auth.models import User
from django.utils import timezone


# Create your models here.


class InventoryItem(models.Model):
    model = models.CharField(max_length=50, verbose_name="Modello")
    brand = models.CharField(max_length=20, verbose_name="Marca")
    kind = models.CharField(max_length=20, verbose_name="Tipo")
    picture = models.ImageField(verbose_name="Foto", null=True, blank=True)
    conditions = models.PositiveIntegerField(
        verbose_name="Condizione", default=5, validators=[MaxValueValidator(5)])
    notes = models.TextField(verbose_name="Note aggiuntive")


class Loans(models.Model):
    fkinventory_item = models.ForeignKey(InventoryItem, models.CASCADE)
    fkuser = models.ForeignKey(User, on_delete=models.PROTECT)
    loan_date = models.DateTimeField(default=timezone.now)
    return_date = models.DateTimeField(null=True, blank=True)
    notification_message = models.PositiveIntegerField(null=True, blank=True)
    warehouse_staff_approved = models.BooleanField(
        verbose_name="Approvazione magazziniere", default=False)

    class Meta:
        permissions = (
            ("can_approve_return", "Può approvare un reso"),
        )
        indexes = [
            models.Index(fields=["id", ]),
            models.Index(fields=["fkinventory_item", ]),
        ]
