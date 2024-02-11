from django.db import models
from hr.models import PersonalEquipmentType


# Create your models here.
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
