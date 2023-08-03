from django.contrib import admin

# Register your models here.

from .models import TelegramLink, PersonalEquipmentType, PersonalEquipmentAssignmentDetail

admin.site.register(TelegramLink)
admin.site.register(PersonalEquipmentType)
admin.site.register(PersonalEquipmentAssignmentDetail)
