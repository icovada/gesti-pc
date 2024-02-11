import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from tg_bot.models import TelegramUser

# Create your models here.


class TelegramLink(models.Model):
    telegram_user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE)
    security_code = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(default=timezone.now)


class PersonalEquipmentType(models.Model):
    kind = models.CharField(max_length=25, verbose_name="Tipo")

    def __str__(self):
        return self.kind


class PersonalEquipmentAssignmentDetail(models.Model):
    fkuser = models.ForeignKey(User, on_delete=models.CASCADE)
    fkequipmentkind = models.ForeignKey(PersonalEquipmentType, on_delete=models.PROTECT)
    size = models.CharField(max_length=10, verbose_name="Taglia", blank=True)
    modello = models.CharField(max_length=20, verbose_name="Modello", blank=True)

    class Meta:
        constraints = [
            models.constraints.UniqueConstraint(
                fields=["fkuser", "fkequipmentkind"],
                name="one_piece_of_equipment_each",
                violation_error_message="Questo volontario ha già un oggetto di questo tipo",
            )
        ]

    def __str__(self):
        return f"{self.fkequipmentkind.kind} di {self.fkuser.username}"


class Certification(models.Model):
    name = models.CharField(max_length=50, verbose_name="Nome")


class TrainingCourse(models.Model):
    name = models.CharField(max_length=50, verbose_name="Nome")
    organizer = models.CharField(max_length=50, verbose_name="Organizzatore")


class TrainingClass(models.Model):
    class ClassTypeEnum(models.IntegerChoices):
        LEZIONE = 1, "Lezione"
        ADDESTRAMENTO = 2, "Addestramento"

    fktrainingcourse = models.ForeignKey(TrainingCourse, on_delete=models.RESTRICT)
    start_date = models.DateTimeField(verbose_name="Inizio")
    end_date = models.DateTimeField(verbose_name="Fine")
    class_type = models.IntegerField(
        choices=ClassTypeEnum.choices, verbose_name="Tipo di lezione"
    )
    uniform_required = models.BooleanField(verbose_name="Divisa richiesta?")
    equipment_required = models.ManyToManyField(
        PersonalEquipmentType, verbose_name="Equipaggiamento richiesto"
    )
