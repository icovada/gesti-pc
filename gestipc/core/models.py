from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from pcroncellobot.models import TelegramUser

# Create your models here.


class Profile(models.Model):
    fkuser = models.OneToOneField(User, on_delete=models.CASCADE)
    address = models.TextField(null=True, blank=True, verbose_name="Indirizzo")
    birth_date = models.DateField(
        null=True, blank=True, verbose_name="Data di nascita")
    blood_type = models.CharField(
        max_length=3, null=True, blank=True, verbose_name="Gruppo sanguigno")
    join_date = models.DateField(
        null=True, blank=True, verbose_name="Data di iscrizione")
    phone_number = models.CharField(
        max_length=14, null=True, blank=True, verbose_name="Numero di telefono")
    clothes_size = models.CharField(
        max_length=20, null=True, blank=True, verbose_name="Taglia abbigliamento")
    shoe_size = models.IntegerField(
        null=True, blank=True, verbose_name="Numero di scarpe")
    illnesses = models.TextField(
        null=True, blank=True, verbose_name="Malattie")
    workplace_name = models.CharField(
        max_length=30, null=True, blank=True, verbose_name="Azienda")
    workplace_vat = models.CharField(
        max_length=11, null=True, blank=True, verbose_name="Azienda - Partita IVA")
    workplace_address = models.TextField(
        null=True, blank=True, verbose_name="Azienda - Indirizzo")
    workplace_phone = models.CharField(
        max_length=13, null=True, blank=True, verbose_name="Azienda - Numero di telefono")
    profile_picture = models.ImageField(null=True, blank=True)
    telegram_user = models.OneToOneField(
        TelegramUser, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["fkuser"])
        ]

    def __str__(self) -> str:
        return self.fkuser.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(fkuser=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
