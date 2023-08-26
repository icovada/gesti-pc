from django.contrib import admin

from .models import (
    PersonalEquipmentAssignmentDetail,
    PersonalEquipmentType,
    TelegramLink,
)

# Register your models here.


admin.site.register(TelegramLink)
admin.site.register(PersonalEquipmentType)
admin.site.register(PersonalEquipmentAssignmentDetail)
