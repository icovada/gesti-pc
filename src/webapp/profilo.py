"""Area personale del volontario: una pagina per sezione, con menu laterale."""

from collections import defaultdict
from datetime import date

from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from magazzino.models import Dotazione
from servizio.models import Timbratura, VolontarioServizioMap
from volontario.models import CertificazioneVolontarioMap

from .reports import _local_midnight
from .views import webapp_view

# (slug, etichetta, icona) nell'ordine del menu.
SEZIONI = [
    ("dati", "Dati personali", "👤"),
    ("dotazioni", "Dotazioni", "🦺"),
    ("formazione", "Formazione", "🎓"),
    ("servizi", "Servizi", "📅"),
    ("ore", "Ore", "⏱️"),
]
_SEZIONI = {slug for slug, _, _ in SEZIONI}


@webapp_view
def profilo(request, sezione: str = "dati"):
    if sezione not in _SEZIONI:
        raise Http404
    volontario = getattr(request.user, "volontario", None)
    context = {"sezioni": SEZIONI, "sezione": sezione, "volontario": volontario}
    if volontario is not None:
        context.update(_LOADERS[sezione](request, volontario))
    return render(request, f"webapp/profilo/{sezione}.html", context)


def _dati(request, volontario) -> dict:
    cf = volontario.codice_fiscale
    try:
        nascita = {"data": cf.birth_date, "luogo": volontario.luogo_di_nascita()}
    except Exception:  # codice fiscale non decodificabile (es. omocodia)
        nascita = None
    tg_user = getattr(volontario, "telegram_user", None)
    return {"nascita": nascita, "telegram_user": tg_user}


def _dotazioni(request, volontario) -> dict:
    dotazioni = Dotazione.objects.filter(volontario=volontario).select_related("tipo")
    return {
        "attive": [d for d in dotazioni if d.is_attivo],
        "restituite": [d for d in dotazioni if not d.is_attivo],
    }


def _formazione(request, volontario) -> dict:
    return {
        "certificazioni": CertificazioneVolontarioMap.objects.filter(
            fkvolontario=volontario
        )
        .select_related("fkcertificazione")
        .order_by("-data_conseguimento")
    }


def _servizi(request, volontario) -> dict:
    now = timezone.now()
    risposte = (
        VolontarioServizioMap.objects.filter(fkvolontario=volontario)
        .select_related("fkservizio", "fkservizio__type")
        .order_by("-fkservizio__data_ora")
    )

    # Minuti lavorati per servizio, per mostrare la presenza effettiva.
    minuti = defaultdict(float)
    for t in Timbratura.objects.filter(
        fkvolontario=volontario, fkservizio__isnull=False, clock_out__isnull=False
    ).only("fkservizio_id", "clock_in", "clock_out"):
        minuti[t.fkservizio_id] += t.duration
    for r in risposte:
        r.minuti = minuti.get(r.fkservizio_id)

    prossimi = [r for r in risposte if r.fkservizio.data_ora >= now]
    prossimi.reverse()  # il più vicino per primo
    return {
        "prossimi": prossimi,
        "passati": [r for r in risposte if r.fkservizio.data_ora < now][:30],
    }


def _ore(request, volontario) -> dict:
    oggi = timezone.localdate()
    anni = sorted(
        {
            timezone.localtime(dt).year
            for dt in Timbratura.objects.filter(fkvolontario=volontario).values_list(
                "clock_in", flat=True
            )
        }
        | {oggi.year},
        reverse=True,
    )
    try:
        anno = int(request.GET.get("anno", oggi.year))
    except ValueError:
        anno = oggi.year
    if anno not in anni:
        anno = oggi.year

    entries = (
        Timbratura.objects.filter(
            fkvolontario=volontario,
            clock_in__gte=_local_midnight(date(anno, 1, 1)),
            clock_in__lt=_local_midnight(date(anno + 1, 1, 1)),
        )
        .select_related("fkservizio", "fkscheduled_task")
        .order_by("-clock_in")
    )
    mesi: dict[int, dict] = {}
    for t in entries:
        mese = timezone.localtime(t.clock_in).month
        gruppo = mesi.setdefault(
            mese, {"data": date(anno, mese, 1), "minuti": 0.0, "voci": []}
        )
        gruppo["voci"].append(t)
        gruppo["minuti"] += t.duration or 0

    return {
        "anni": anni,
        "anno": anno,
        "mesi": list(mesi.values()),
        "minuti_anno": sum(m["minuti"] for m in mesi.values()),
    }


_LOADERS = {
    "dati": _dati,
    "dotazioni": _dotazioni,
    "formazione": _formazione,
    "servizi": _servizi,
    "ore": _ore,
}
