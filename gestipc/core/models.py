from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import uuid

# Create your models here.


class Profile(models.Model):
    fkuser = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.CharField(max_length=80, null=True)
    birth_date = models.DateField(null=True)
    blood_type = models.CharField(max_length=3, null=True)
    join_date = models.DateField(null=True)
    phone_number = models.CharField(max_length=12, null=True)
    profile_picture = models.ImageField()
    telegram_user_id = models.CharField(max_length=20, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["fkuser"])
        ]
        constraints = [
            models.constraints.UniqueConstraint(
                fields=["fkuser"], name="one_profile_per_user"
            ),
            models.constraints.UniqueConstraint(
                fields=["telegram_user_id"], name="one_telegram_per_person"
            )
        ]


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(fkuser=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class TelegramLink(models.Model):
    telegram_user = models.CharField(max_length=20)
    security_code = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(default=timezone.now)
