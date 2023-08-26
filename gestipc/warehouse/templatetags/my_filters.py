from django import template

register = template.Library()


# Black magic from https://stackoverflow.com/questions/1107737/numeric-for-loop-in-django-templates
@register.filter(name="times")
def times(number):
    return range(number)
