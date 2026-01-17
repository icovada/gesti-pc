from django.contrib.auth import login
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from .models import LoginToken


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
