"""Aggregazioni delle ore di servizio (Timbratura) per i report della web app."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from servizio.models import Timbratura

MESI = [
    "gen",
    "feb",
    "mar",
    "apr",
    "mag",
    "giu",
    "lug",
    "ago",
    "set",
    "ott",
    "nov",
    "dic",
]

# Categoria di attività di una timbratura, in ordine fisso (determina i colori).
CATEGORIE = [
    ("servizio", "Servizi"),
    ("attivita", "Attività programmate"),
    ("altro", "Altro"),
]


def _categoria(t: Timbratura) -> str:
    if t.fkservizio_id:
        return "servizio"
    if t.fkscheduled_task_id:
        return "attivita"
    return "altro"


def _local_midnight(d: date) -> datetime:
    return timezone.make_aware(datetime.combine(d, time.min))


def timbrature_periodo(start: date, end: date):
    """Timbrature con entrata tra start ed end inclusi (ora locale)."""
    return Timbratura.objects.filter(
        clock_in__gte=_local_midnight(start),
        clock_in__lt=_local_midnight(end + timedelta(days=1)),
    )


def month_range(start: date, end: date) -> list[tuple[int, int]]:
    """Tutti i mesi (anno, mese) da start a end inclusi."""
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


@dataclass
class VolontarioOre:
    codice_fiscale: str
    nome: str
    ore: float = 0.0
    turni: int = 0
    per_categoria: dict[str, float] = field(
        default_factory=lambda: {k: 0.0 for k, _ in CATEGORIE}
    )
    ultima_entrata: datetime | None = None


@dataclass
class ReportOre:
    start: date
    end: date
    ore_totali: float
    turni: int
    volontari_attivi: int
    turni_aperti: int
    mesi: list[dict]
    per_volontario: list[VolontarioOre]

    @property
    def media_per_volontario(self) -> float:
        if not self.volontari_attivi:
            return 0.0
        return self.ore_totali / self.volontari_attivi


def hours_report(start: date, end: date) -> ReportOre:
    """Ore completate (con uscita registrata) con entrata tra start ed end inclusi.

    Una timbratura viene attribuita interamente al mese della sua entrata.
    """
    qs = (
        timbrature_periodo(start, end)
        .filter(clock_out__isnull=False)
        .select_related("fkvolontario")
        .only(
            "clock_in",
            "clock_out",
            "fkservizio_id",
            "fkscheduled_task_id",
            "fkvolontario__codice_fiscale",
            "fkvolontario__nome",
            "fkvolontario__cognome",
        )
    )

    mesi = {ym: {k: 0.0 for k, _ in CATEGORIE} for ym in month_range(start, end)}
    volontari: dict[str, VolontarioOre] = {}
    ore_totali = 0.0
    turni = 0

    for t in qs:
        ore = (t.clock_out - t.clock_in).total_seconds() / 3600
        if ore <= 0:
            continue
        cat = _categoria(t)
        local_in = timezone.localtime(t.clock_in)
        mesi[(local_in.year, local_in.month)][cat] += ore

        cf = str(t.fkvolontario.codice_fiscale)
        v = volontari.get(cf)
        if v is None:
            v = volontari[cf] = VolontarioOre(
                codice_fiscale=cf,
                nome=f"{t.fkvolontario.nome} {t.fkvolontario.cognome}",
            )
        v.ore += ore
        v.turni += 1
        v.per_categoria[cat] += ore
        if v.ultima_entrata is None or t.clock_in > v.ultima_entrata:
            v.ultima_entrata = t.clock_in

        ore_totali += ore
        turni += 1

    return ReportOre(
        start=start,
        end=end,
        ore_totali=ore_totali,
        turni=turni,
        volontari_attivi=len(volontari),
        turni_aperti=Timbratura.objects.filter(clock_out__isnull=True).count(),
        mesi=[
            {"label": f"{MESI[m - 1]} {y % 100:02d}", "anno": y, "mese": m, **ore}
            for (y, m), ore in mesi.items()
        ],
        per_volontario=sorted(volontari.values(), key=lambda v: (-v.ore, v.nome)),
    )


def personal_hours(volontario, today: date) -> dict:
    """Riepilogo ore del singolo volontario per la home page."""
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    entries = Timbratura.objects.filter(
        fkvolontario=volontario,
        clock_out__isnull=False,
        clock_in__gte=_local_midnight(year_start),
    ).only("clock_in", "clock_out")

    ore_mese = ore_anno = 0.0
    month_start_dt = _local_midnight(month_start)
    for t in entries:
        ore = max((t.clock_out - t.clock_in).total_seconds() / 3600, 0)
        ore_anno += ore
        if t.clock_in >= month_start_dt:
            ore_mese += ore

    return {
        "ore_mese": ore_mese,
        "ore_anno": ore_anno,
        "turno_aperto": Timbratura.objects.filter(
            fkvolontario=volontario, clock_out__isnull=True
        )
        .select_related("fkservizio", "fkscheduled_task")
        .first(),
        "ultime": Timbratura.objects.filter(fkvolontario=volontario)
        .select_related("fkservizio", "fkscheduled_task")
        .order_by("-clock_in")[:5],
    }
