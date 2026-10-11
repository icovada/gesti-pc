"""Notifica "in servizio" a ogni entrata/uscita, da qualunque canale (app, bot, admin)."""

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from servizio.models import Timbratura

from . import push

# La notifica "in servizio" deve sopravvivere a un turno lungo.
TTL_TURNO = 12 * 3600


@receiver(pre_save, sender=Timbratura)
def _remember_clock_out(sender, instance: Timbratura, **kwargs):
    if instance._state.adding:
        instance._previous_clock_out = None
    else:
        instance._previous_clock_out = (
            Timbratura.objects.filter(pk=instance.pk)
            .values_list("clock_out", flat=True)
            .first()
        )


@receiver(post_save, sender=Timbratura)
def notify_turno(sender, instance: Timbratura, created: bool, **kwargs):
    if not push.is_configured():
        return

    if created and instance.clock_out is None:
        payload, ttl = push.notifica_in_servizio(instance), TTL_TURNO
    elif (
        not created
        and instance.clock_out is not None
        and getattr(instance, "_previous_clock_out", None) is None
    ):
        payload, ttl = push.notifica_uscita(instance), 3600
    else:
        return

    volontario_id = str(instance.fkvolontario_id)
    transaction.on_commit(
        lambda: push.send_push_background(volontario_id, payload, ttl)
    )
