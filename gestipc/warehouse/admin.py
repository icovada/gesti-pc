from django.contrib import admin

# Register your models here.
from .models import InventoryItem, Loan

admin.site.register(InventoryItem)
admin.site.register(Loan)
