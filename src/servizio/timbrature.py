"""Logica di entrata/uscita condivisa tra web app e notifiche push (non il bot)."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from tg_bot.notify import invia_messaggio_entrata_background
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
