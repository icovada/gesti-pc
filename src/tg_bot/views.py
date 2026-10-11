import logging

from django.contrib import messages
from django.contrib.auth import login
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET

from . import oidc
from .models import LoginToken, TelegramUser

logger = logging.getLogger(__name__)

LOGIN_NEXT_SESSION_KEY = "login_next"
OIDC_SESSION_KEY = "telegram_oidc"


def _remember_next(request) -> None:
    """Salva in sessione la pagina da aprire dopo il login (?next=...)."""
    next_url = request.GET.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        request.session[LOGIN_NEXT_SESSION_KEY] = next_url


def _post_login_url(request) -> str:
    """Pagina di destinazione dopo il login: ?next salvato, altrimenti la web app.

    Va letto prima di login(), che rigenera la sessione mantenendone i dati.
    """
    return request.session.pop(LOGIN_NEXT_SESSION_KEY, None) or reverse("webapp:home")


def _login_failed(request, message: str):
    messages.error(request, message)
    return redirect("landing")


def token_login(request, token: str):
    """Authenticate user via one-time Telegram login token."""
    try:
        login_token = LoginToken.objects.select_related(
            "telegram_user__volontario__user"
        ).get(token=token)
    except LoginToken.DoesNotExist:
        return HttpResponse(
            "Link non valido o scaduto.",
            status=400,
        )

    if not login_token.is_valid:
        return HttpResponse(
            "Link scaduto o già utilizzato. Richiedi un nuovo link con /login nel bot.",
            status=400,
        )

    # Get the Django user
    volontario = login_token.telegram_user.volontario
    if not volontario or not volontario.user:
        return HttpResponse(
            "Account non configurato correttamente. Contatta l'amministratore.",
            status=400,
        )

    # Mark token as used
    login_token.used_at = timezone.now()
    login_token.save(update_fields=["used_at"])

    # Log the user in
    login(request, volontario.user)

    return redirect(reverse("webapp:home"))


@require_GET
def telegram_login(request):
    """Avvia il login con Telegram (OpenID Connect): rimanda a oauth.telegram.org."""
    if not oidc.is_configured():
        return _login_failed(request, "Il login con Telegram non è configurato.")

    _remember_next(request)
    login_state = oidc.new_login_state()
    try:
        url = oidc.authorization_url(login_state)
    except Exception:
        logger.exception("Telegram OIDC discovery failed")
        return _login_failed(request, "Telegram non è raggiungibile. Riprova.")
    request.session[OIDC_SESSION_KEY] = login_state
    return redirect(url)


@require_GET
def telegram_callback(request):
    """Ritorno da oauth.telegram.org: verifica l'identità e apre la sessione."""
    login_state = request.session.pop(OIDC_SESSION_KEY, None)
    if request.GET.get("error"):
        return _login_failed(request, "Accesso annullato.")
    if not login_state or request.GET.get("state") != login_state["state"]:
        return _login_failed(request, "Richiesta di accesso scaduta. Riprova.")

    try:
        id_token = oidc.exchange_code(
            request.GET.get("code", ""), login_state["verifier"]
        )
        claims = oidc.verify_id_token(id_token, login_state["nonce"])
    except oidc.OIDCError as e:
        logger.warning("Telegram OIDC login failed: %s", e.__cause__ or e)
        return _login_failed(request, str(e))

    tg_user = (
        TelegramUser.objects.select_related("volontario__user")
        .filter(telegram_id=claims["id"])
        .first()
    )
    volontario = tg_user.volontario if tg_user else None
    if volontario is None:
        return _login_failed(
            request,
            "Il tuo account Telegram non è collegato a un volontario. "
            "Scrivi /start al bot per collegarlo, poi riprova.",
        )
    if volontario.user is None or not volontario.user.is_active:
        return _login_failed(
            request, "Account non abilitato. Contatta un amministratore."
        )

    next_url = _post_login_url(request)
    login(request, volontario.user)
    return redirect(next_url)
