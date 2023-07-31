from django.db import models
from django.utils import timezone
import uuid

# Create your models here.
class TelegramLink(models.Model):
    telegram_user_id = models.CharField(max_length=20)
    security_code = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(default=timezone.now)
