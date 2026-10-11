"""Logica di entrata/uscita condivisa tra web app e notifiche push."""

from django.db.models import Q
from django.utils import timezone

from volontario.models import Volontario

from .models import Servizio, Timbratura


class TimbraturaError(Exception):
    """Operazione di timbratura non possibile; il messaggio è per l'utente."""


def servizio_in_corso(now=None) -> Servizio | None:
    """Il servizio iniziato più di recente e non ancora terminato, se esiste."""
    now = now or timezone.now()
    return (
        Servizio.objects.filter(data_ora__lte=now)
        .filter(Q(data_ora_fine__gte=now) | Q(data_ora_fine__isnull=True))
        .order_by("-data_ora")
        .first()
    )


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
    return Timbratura.objects.create(
        fkvolontario=volontario, fkservizio=servizio or servizio_in_corso()
    )


def registra_uscita(volontario: Volontario) -> Timbratura:
    """Chiude la timbratura aperta del volontario."""
    aperta = turno_aperto(volontario)
    if aperta is None:
        raise TimbraturaError("Non hai nessuna entrata aperta.")
    aperta.clock_out = timezone.now()
    aperta.save(update_fields=["clock_out"])
    return aperta
