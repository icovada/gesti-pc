import logging
from enum import Enum, auto

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from django.conf import settings

from .models import TelegramUser
from volontario.models import Volontario

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    WAITING_CODICE_FISCALE = auto()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Handle the /start command."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Get or create TelegramUser
    tg_user, created = await TelegramUser.objects.aget_or_create(
        telegram_id=user.id,
        defaults={
            "chat_id": chat_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
    )

    # Update user info if changed
    if not created:
        tg_user.chat_id = chat_id
        tg_user.username = user.username
        tg_user.first_name = user.first_name
        tg_user.last_name = user.last_name
        await tg_user.asave()

    if tg_user.is_linked:
        volontario = await Volontario.objects.aget(pk=tg_user.volontario_id)
        await update.message.reply_text(
            f"Bentornato, {volontario.nome}! 👋\n\n"
            f"Il tuo account è già associato.\n"
            f"Usa /help per vedere i comandi disponibili."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"Ciao {user.first_name}! 👋\n\n"
        f"Benvenuto nel bot di gestione volontari.\n\n"
        f"Per associare il tuo account Telegram al tuo profilo volontario, "
        f"inserisci il tuo codice fiscale:"
    )
    return ConversationState.WAITING_CODICE_FISCALE.value


async def handle_codice_fiscale(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle codice fiscale input for association."""
    user = update.effective_user
    codice_fiscale = update.message.text.strip().upper()

    # Validate length
    if len(codice_fiscale) != 16:
        await update.message.reply_text(
            "❌ Il codice fiscale deve essere di 16 caratteri.\n"
            "Riprova o usa /annulla per annullare."
        )
        return ConversationState.WAITING_CODICE_FISCALE.value

    # Check if volontario exists
    try:
        volontario = await Volontario.objects.aget(codice_fiscale=codice_fiscale)
    except Volontario.DoesNotExist:
        await update.message.reply_text(
            "❌ Codice fiscale non trovato nel sistema.\n\n"
            "Verifica di aver inserito il codice correttamente o contatta "
            "l'amministratore se non sei ancora registrato.\n\n"
            "Riprova o usa /annulla per annullare."
        )
        return ConversationState.WAITING_CODICE_FISCALE.value

    # Check if volontario is already linked to another telegram account
    existing_link = await TelegramUser.objects.filter(
        volontario=volontario
    ).exclude(telegram_id=user.id).afirst()

    if existing_link:
        await update.message.reply_text(
            "❌ Questo volontario è già associato ad un altro account Telegram.\n\n"
            "Se pensi sia un errore, contatta l'amministratore."
        )
        return ConversationHandler.END

    # Link the accounts
    tg_user = await TelegramUser.objects.aget(telegram_id=user.id)
    tg_user.volontario = volontario
    await tg_user.asave()

    await update.message.reply_text(
        f"✅ Associazione completata!\n\n"
        f"Benvenuto, {volontario.nome} {volontario.cognome}!\n"
        f"Organizzazione: {volontario.fkorganizzazione or 'Non assegnata'}\n\n"
        f"Usa /help per vedere i comandi disponibili."
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation."""
    await update.message.reply_text(
        "Operazione annullata.\n"
        "Usa /start per ricominciare."
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available commands."""
    user = update.effective_user

    try:
        tg_user = await TelegramUser.objects.aget(telegram_id=user.id)
        if tg_user.is_linked:
            await update.message.reply_text(
                "📋 Comandi disponibili:\n\n"
                "/start - Avvia il bot\n"
                "/profilo - Visualizza il tuo profilo\n"
                "/help - Mostra questo messaggio"
            )
            return
    except TelegramUser.DoesNotExist:
        pass

    await update.message.reply_text(
        "📋 Comandi disponibili:\n\n"
        "/start - Avvia il bot e associa il tuo account\n"
        "/help - Mostra questo messaggio"
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user profile."""
    user = update.effective_user

    try:
        tg_user = await TelegramUser.objects.select_related("volontario").aget(
            telegram_id=user.id
        )
    except TelegramUser.DoesNotExist:
        await update.message.reply_text(
            "❌ Non sei ancora registrato.\n"
            "Usa /start per associare il tuo account."
        )
        return

    if not tg_user.is_linked:
        await update.message.reply_text(
            "❌ Il tuo account Telegram non è ancora associato.\n"
            "Usa /start per completare l'associazione."
        )
        return

    volontario = tg_user.volontario
    # Need to fetch related org separately for async
    org_name = "Non assegnata"
    if volontario.fkorganizzazione_id:
        from volontario.models import Organizzazione
        try:
            org = await Organizzazione.objects.aget(pk=volontario.fkorganizzazione_id)
            org_name = org.name
        except Organizzazione.DoesNotExist:
            pass

    await update.message.reply_text(
        f"👤 Il tuo profilo:\n\n"
        f"Nome: {volontario.nome} {volontario.cognome}\n"
        f"Codice Fiscale: {volontario.codice_fiscale}\n"
        f"Organizzazione: {org_name}"
    )


def create_application() -> Application:
    """Create and configure the bot application."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN non configurato in settings.py")

    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Conversation handler for /start and association flow
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ConversationState.WAITING_CODICE_FISCALE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_codice_fiscale),
            ],
        },
        fallbacks=[
            CommandHandler("annulla", cancel),
            CommandHandler("cancel", cancel),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profilo", profile))

    return application


def run_bot() -> None:
    """Run the bot in polling mode."""
    application = create_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
