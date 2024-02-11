from django.contrib import admin

from .models import (
    PersonalEquipmentAssignmentDetail,
    PersonalEquipmentType,
    TelegramLink,
    Certification,
    TrainingCourse,
    TrainingClass,
)

# Register your models here.


admin.site.register(TelegramLink)
admin.site.register(PersonalEquipmentType)
admin.site.register(PersonalEquipmentAssignmentDetail)
admin.site.register(Certification)
admin.site.register(TrainingCourse)
admin.site.register(TrainingClass)
