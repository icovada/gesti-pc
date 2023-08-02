import uuid
from django.db import models
from django.utils import timezone
from pcroncellobot.models import TelegramUser

# Create your models here.
class TelegramLink(models.Model):
    telegram_user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE)
    security_code = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(default=timezone.now)
  