"""Messaggi Telegram inviati da fuori dal bot (web app, notifiche push).

Il processo web non ha l'Application del bot: usa un Bot "usa e getta" in un
thread separato, così la richiesta HTTP non aspetta Telegram. I pulsanti
inviati qui sono gestiti dal processo del bot come quelli dei suoi messaggi.
"""

import asyncio
import html
import logging
import threading

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from servizio.models import Timbratura

from .models import TelegramUser

logger = logging.getLogger(__name__)

CLOCK_OUT_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🔴 Registra uscita", callback_data="clock_out")]]
)


def testo_entrata(entry: Timbratura) -> str:
    ora = f"{timezone.localtime(entry.clock_in):%H:%M}"
    if entry.fkservizio_id:
        servizio = html.escape(entry.fkservizio.nome)
        return (
            f"✅ Entrata registrata dall'app alle {ora} "
            f"per il servizio <b>{servizio}</b>.\n\nBuon lavoro!"
        )
    return f"✅ Entrata registrata dall'app alle {ora}.\n\nBuon lavoro!"


async def _send(chat_id: int, text: str) -> None:
    async with Bot(token=settings.TELEGRAM_BOT_TOKEN) as bot:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=CLOCK_OUT_KEYBOARD,
        )


def invia_messaggio_entrata(entry_pk) -> None:
    """Manda in chat privata la conferma d'entrata con il pulsante per l'uscita."""
    entry = Timbratura.objects.select_related("fkservizio").filter(pk=entry_pk).first()
    if entry is None or entry.clock_out is not None:
        return
    tg_user = TelegramUser.objects.filter(volontario_id=entry.fkvolontario_id).first()
    if tg_user is None:
        return
    try:
        asyncio.run(_send(tg_user.telegram_id, testo_entrata(entry)))
    except Exception:
        logger.exception("Failed to send clock-in message to %s", tg_user.telegram_id)


def invia_messaggio_entrata_background(entry_pk) -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return

    def run():
        try:
            invia_messaggio_entrata(entry_pk)
        finally:
            close_old_connections()

    threading.Thread(target=run, daemon=True).start()
