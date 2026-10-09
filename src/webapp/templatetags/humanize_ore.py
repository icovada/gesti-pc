from django import template

register = template.Library()


@register.filter
def ore(hours) -> str:
    """Ore decimali → "12h 30m" (o "45m" sotto l'ora)."""
    total_minutes = round((hours or 0) * 60)
    h, m = divmod(total_minutes, 60)
    if not m:
        return f"{h}h"
    return f"{h}h {m:02d}m" if h else f"{m}m"


@register.filter
def minuti_ore(minutes) -> str:
    return ore((minutes or 0) / 60)


@register.filter
def get_item(mapping, key):
    return mapping.get(key)
