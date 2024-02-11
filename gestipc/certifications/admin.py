from django.contrib import admin

from .models import Certification, TrainingCourse, TrainingClass, TrainingEnrollment

# Register your models here.
admin.site.register(Certification)
admin.site.register(TrainingCourse)
admin.site.register(TrainingClass)
admin.site.register(TrainingEnrollment)
