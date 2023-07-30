from django.contrib import admin

# Register your models here.
admin.site.site_header = "Gesti-PC"
# default: "Site administration"
admin.site.index_title = "Gesti-PC admin"
# default: "Django site admin"
admin.site.site_title = "Gesti-PC"

from core.models import Profile

admin.site.register(Profile)
