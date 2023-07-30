from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.


class Profile(models.Model):
    fkuser = models.OneToOneField(User, on_delete=models.CASCADE)
    address = models.CharField(max_length=80, null=True)
    birth_date = models.DateField(null=True)
    blood_type = models.CharField(max_length=3, null=True)
    join_date = models.DateField(null=True)
    phone_number = models.CharField(max_length=12, null=True)
    profile_picture = models.ImageField()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
