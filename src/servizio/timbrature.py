"""Logica di entrata/uscita condivisa tra web app e notifiche push (non il bot)."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from tg_bot.notify import (
    invia_messaggi_servizio_terminato_background,
    invia_messaggio_entrata_background,
)
from volontario.models import Volontario

from .models import Servizio, Timbratura


class TimbraturaError(Exception):
    """Operazione di timbratura non possibile; il messaggio è per l'utente."""


# Chi entra poco prima dell'inizio viene comunque collegato al servizio.
ANTICIPO_ENTRATA = timedelta(hours=1)


def servizi_in_corso(now=None) -> QuerySet[Servizio]:
    """Servizi non ancora terminati e iniziati (o in partenza entro `ANTICIPO_ENTRATA`).

    Il più recente viene prima.
    """
    now = now or timezone.now()
    return (
        Servizio.objects.filter(data_ora__lte=now + ANTICIPO_ENTRATA)
        .filter(Q(data_ora_fine__gte=now) | Q(data_ora_fine__isnull=True))
        .order_by("-data_ora")
    )


def servizio_in_corso(now=None) -> Servizio | None:
    """Il servizio a cui collegare un'entrata registrata adesso, se esiste."""
    return servizi_in_corso(now).first()


def turno_aperto(volontario: Volontario) -> Timbratura | None:
    return Timbratura.objects.filter(
        fkvolontario=volontario, clock_out__isnull=True
    ).first()


def registra_entrata(
    volontario: Volontario, servizio: Servizio | None = None
) -> Timbratura:
    """Apre una timbratura, collegata al servizio indicato o a quello in corso."""
    aperta = turno_aperto(volontario)
    if aperta:
        raise TimbraturaError(
            "Hai già un'entrata aperta dalle "
            f"{timezone.localtime(aperta.clock_in):%H:%M del %d/%m/%Y}."
        )
    entry = Timbratura.objects.create(
        fkvolontario=volontario, fkservizio=servizio or servizio_in_corso()
    )
    # Le entrate dal bot hanno già il loro messaggio; quelle dall'app o dalle
    # notifiche ricevono in chat il pulsante per registrare l'uscita.
    transaction.on_commit(lambda: invia_messaggio_entrata_background(entry.pk))
    return entry


def registra_uscita(volontario: Volontario) -> Timbratura:
    """Chiude la timbratura aperta del volontario."""
    aperta = turno_aperto(volontario)
    if aperta is None:
        raise TimbraturaError("Non hai nessuna entrata aperta.")
    aperta.clock_out = timezone.now()
    aperta.save(update_fields=["clock_out"])
    return aperta


def turni_aperti_per_servizio() -> list[tuple[Servizio, list[Timbratura]]]:
    """I servizi con volontari ancora in servizio, con le rispettive timbrature aperte."""
    aperte = (
        Timbratura.objects.filter(clock_out__isnull=True, fkservizio__isnull=False)
        .select_related("fkservizio", "fkvolontario")
        .order_by("fkservizio__data_ora", "fkvolontario__cognome", "fkvolontario__nome")
    )
    per_servizio: dict[Servizio, list[Timbratura]] = {}
    for t in aperte:
        per_servizio.setdefault(t.fkservizio, []).append(t)
    return list(per_servizio.items())


def termina_servizio(servizio: Servizio) -> list[Timbratura]:
    """Termina il servizio adesso e registra l'uscita di chi è ancora in servizio."""
    now = timezone.now()
    with transaction.atomic():
        aperte = list(
            Timbratura.objects.filter(fkservizio=servizio, clock_out__isnull=True)
        )
        for t in aperte:
            t.clock_out = now
            t.save(update_fields=["clock_out"])
        # Se era ancora in corso, finisce adesso: niente più entrate collegate né promemoria.
        if servizio.data_ora <= now and (
            servizio.data_ora_fine is None or servizio.data_ora_fine > now
        ):
            Servizio.objects.filter(pk=servizio.pk).update(
                data_ora_fine=now, end_reminder_sent=True
            )
        pks = [t.pk for t in aperte]
        transaction.on_commit(lambda: invia_messaggi_servizio_terminato_background(pks))
    return aperte
