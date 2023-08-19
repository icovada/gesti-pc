from django import forms
from django.forms import fields
from django.contrib.auth.models import User


class UserMultipleChoiceForm(forms.Form):
    """Creates a form with a single user choice field

    Args:
        user_queryset (_type_): QuerySet for user choice
    """
    user = forms.ModelChoiceField(queryset=User.objects.all())

    def __init__(self, user_queryset, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = user_queryset