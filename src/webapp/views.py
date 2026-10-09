import csv
import logging
from datetime import date
from functools import wraps

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST

from tg_bot.models import TelegramUser

from .reports import CATEGORIE, hours_report, personal_hours
from .telegram_auth import validate_init_data

logger = logging.getLogger(__name__)

PRESETS = [
    ("mese", "Mese corrente"),
    ("3m", "Ultimi 3 mesi"),
    ("12m", "Ultimi 12 mesi"),
    ("anno", "Anno corrente"),
]


def webapp_view(view):
    """Pagina della web app: incorporabile in Telegram e protetta da login.

    Gli utenti non autenticati vedono una pagina "gate" che, dentro Telegram,
    si autentica in automatico con initData; nel browser rimanda al login web.
    """

    @xframe_options_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return render(request, "webapp/gate.html", status=401)
        return view(request, *args, **kwargs)

    return wrapper


def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return render(request, "webapp/forbidden.html", status=403)
        return view(request, *args, **kwargs)

    return wrapper


@require_POST
def telegram_auth(request):
    """Login automatico da Telegram Mini App tramite initData firmato."""
    user_data = validate_init_data(
        request.POST.get("init_data", ""), settings.TELEGRAM_BOT_TOKEN or ""
    )
    if user_data is None:
        return JsonResponse(
            {"ok": False, "error": "Dati Telegram non validi."}, status=403
        )

    tg_user = (
        TelegramUser.objects.select_related("volontario__user")
        .filter(telegram_id=user_data["id"])
        .first()
    )
    volontario = tg_user.volontario if tg_user else None
    if volontario is None:
        return JsonResponse(
            {
                "ok": False,
                "error": "Account non collegato. Usa /start nel bot per collegarlo.",
            },
            status=403,
        )
    if volontario.user is None or not volontario.user.is_active:
        return JsonResponse(
            {
                "ok": False,
                "error": "Account non abilitato. Contatta un amministratore.",
            },
            status=403,
        )

    login(request, volontario.user)
    return JsonResponse({"ok": True})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("web_login")


@webapp_view
def home(request):
    volontario = getattr(request.user, "volontario", None)
    context = {"volontario": volontario}
    if volontario is not None:
        context.update(personal_hours(volontario, timezone.localdate()))
    return render(request, "webapp/home.html", context)


def _shift_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def _parse_range(params, today: date) -> tuple[date, date, str]:
    """Restituisce (inizio, fine, preset) dai parametri GET; default ultimi 12 mesi."""
    try:
        start = date.fromisoformat(params.get("da", ""))
        end = date.fromisoformat(params.get("a", ""))
        if start <= end:
            return start, end, ""
    except ValueError:
        pass

    preset = params.get("periodo", "12m")
    month_start = today.replace(day=1)
    if preset == "mese":
        return month_start, today, preset
    if preset == "3m":
        return _shift_months(month_start, -2), today, preset
    if preset == "anno":
        return today.replace(month=1, day=1), today, preset
    return _shift_months(month_start, -11), today, "12m"


@webapp_view
@staff_required
def report_ore(request):
    start, end, preset = _parse_range(request.GET, timezone.localdate())
    report = hours_report(start, end)

    if request.GET.get("formato") == "csv":
        return _report_csv(report)

    chart_data = {
        "categorie": [{"key": k, "label": label} for k, label in CATEGORIE],
        "mesi": report.mesi,
        "volontari": [
            {"nome": v.nome, "ore": round(v.ore, 2)} for v in report.per_volontario
        ],
    }
    return render(
        request,
        "webapp/report_ore.html",
        {
            "report": report,
            "presets": PRESETS,
            "preset": preset,
            "chart_data": chart_data,
            "categorie": CATEGORIE,
            "csv_query": request.GET.urlencode(),
        },
    )


def _report_csv(report) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="ore_{report.start:%Y%m%d}_{report.end:%Y%m%d}.csv"'
    )
    response.write("﻿")  # BOM: Excel riconosce l'UTF-8
    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        ["Codice fiscale", "Volontario", "Ore totali", "Turni"]
        + [label for _, label in CATEGORIE]
    )
    for v in report.per_volontario:
        writer.writerow(
            [v.codice_fiscale, v.nome, _fmt(v.ore), v.turni]
            + [_fmt(v.per_categoria[k]) for k, _ in CATEGORIE]
        )
    return response


def _fmt(hours: float) -> str:
    return f"{hours:.2f}".replace(".", ",")
