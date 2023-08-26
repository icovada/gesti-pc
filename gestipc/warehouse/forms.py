from django import forms

from .models import InventoryItem


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            "model",
            "brand",
            "kind",
            "picture",
            "conditions",
            "notes",
        ]


class InventoryItemEditForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            "picture",
            "conditions",
            "notes",
        ]
