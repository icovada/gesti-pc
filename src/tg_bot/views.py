import asyncio
import logging

from django.conf import settings
from django.contrib.auth import login
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from volontario.models import Volontario

from .models import LoginToken, TelegramUser, WebLoginRequest

logger = logging.getLogger(__name__)


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

    # Redirect to admin (or homepage when available)
    return redirect("admin:index")


async def _send_login_approval_message(chat_id: int, volontario: Volontario, token: str) -> int | None:
    """Send login approval message with inline keyboard. Returns message_id."""
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not configured")
        return None

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approva", callback_data=f"web_login:approve:{token}"),
            InlineKeyboardButton("❌ Rifiuta", callback_data=f"web_login:deny:{token}"),
        ]
    ])

    bot = Bot(token=bot_token)
    async with bot:
        message = await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🔐 *Richiesta di accesso web*\n\n"
                f"Qualcuno sta cercando di accedere come:\n"
                f"*{volontario.nome} {volontario.cognome}*\n\n"
                f"Se sei tu, premi Approva. Altrimenti premi Rifiuta."
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    return message.message_id


@require_http_methods(["GET", "POST"])
def web_login(request):
    """Handle web login via codice fiscale."""
    error = None
    codice_fiscale = ""

    if request.method == "POST":
        codice_fiscale = request.POST.get("codice_fiscale", "").strip().upper()

        if not codice_fiscale:
            error = "Inserisci il codice fiscale."
        else:
            try:
                volontario = Volontario.objects.get(codice_fiscale=codice_fiscale)
            except Volontario.DoesNotExist:
                error = "Codice fiscale non trovato. Verifica di essere registrato."
            else:
                # Check if volontario has a linked TelegramUser
                try:
                    telegram_user = volontario.telegram_user
                except TelegramUser.DoesNotExist:
                    error = "Account Telegram non collegato. Usa il bot per collegare il tuo account."
                else:
                    # Create a web login request
                    login_request = WebLoginRequest.objects.create(
                        volontario=volontario,
                        telegram_user=telegram_user,
                    )

                    # Send Telegram message with approval buttons
                    message_id = asyncio.run(
                        _send_login_approval_message(
                            telegram_user.chat_id,
                            volontario,
                            login_request.token,
                        )
                    )

                    if message_id:
                        login_request.telegram_message_id = message_id
                        login_request.save(update_fields=["telegram_message_id"])

                        return render(request, "tg_bot/web_login_pending.html", {
                            "volontario": volontario,
                            "token": login_request.token,
                        })
                    else:
                        login_request.delete()
                        error = "Errore nell'invio del messaggio Telegram. Riprova."

    return render(request, "tg_bot/web_login.html", {
        "error": error,
        "codice_fiscale": codice_fiscale,
    })


@require_GET
def web_login_status(request, token: str):
    """Check status of a web login request (polled by frontend)."""
    try:
        login_request = WebLoginRequest.objects.select_related(
            "volontario__user"
        ).get(token=token)
    except WebLoginRequest.DoesNotExist:
        return JsonResponse({"status": "not_found"}, status=404)

    # Check if expired
    if login_request.status == WebLoginRequest.Status.PENDING and not login_request.is_pending:
        login_request.status = WebLoginRequest.Status.EXPIRED
        login_request.save(update_fields=["status"])

    if login_request.status == WebLoginRequest.Status.APPROVED:
        # Log the user in
        volontario = login_request.volontario
        if volontario.user:
            login(request, volontario.user)
            return JsonResponse({
                "status": "approved",
                "redirect_url": "/admin/",
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": "Account non configurato correttamente.",
            })

    return JsonResponse({"status": login_request.status})
