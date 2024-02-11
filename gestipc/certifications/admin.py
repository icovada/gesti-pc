from django.contrib import admin

from .models import Certification, TrainingCourse, TrainingClass

# Register your models here.
admin.site.register(Certification)
admin.site.register(TrainingCourse)
admin.site.register(TrainingClass)
