import logging
from datetime import datetime
from enum import Enum, auto

from django.utils import timezone
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PollAnswerHandler,
    filters,
)

from django.conf import settings
from django.contrib.auth import get_user_model

from .models import LoginToken, TelegramUser
from servizio.models import Servizio, Timbratura, VolontarioServizioMap
from volontario.models import Volontario

User = get_user_model()

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    WAITING_CODICE_FISCALE = auto()
    WAITING_SERVIZIO_NAME = auto()
    WAITING_SERVIZIO_DATE = auto()


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

    # Check if volontario exists (with org preloaded)
    try:
        volontario = await Volontario.objects.select_related("fkorganizzazione").aget(
            codice_fiscale=codice_fiscale
        )
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

    # Create Django User if not already linked
    if not volontario.user_id:
        username = f"v_{codice_fiscale.lower()}"
        django_user = await User.objects.acreate_user(
            username=username,
            first_name=volontario.nome,
            last_name=volontario.cognome,
        )
        volontario.user = django_user
        await volontario.asave(update_fields=["user"])

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
                "/entrata - Registra entrata\n"
                "/uscita - Registra uscita\n"
                "/ore - Riepilogo ore del mese\n"
                "/nuovoservizio - Crea un nuovo servizio\n"
                "/login - Ottieni link di accesso al sito\n"
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


async def get_linked_volontario(update: Update) -> Volontario | None:
    """Helper to get linked volontario or send error message."""
    user = update.effective_user
    try:
        tg_user = await TelegramUser.objects.aget(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text(
            "❌ Non sei ancora registrato.\n"
            "Usa /start per associare il tuo account."
        )
        return None

    if not tg_user.is_linked:
        await update.message.reply_text(
            "❌ Il tuo account Telegram non è ancora associato.\n"
            "Usa /start per completare l'associazione."
        )
        return None

    return await Volontario.objects.aget(pk=tg_user.volontario_id)


async def clock_in(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clock in - start tracking time."""
    volontario = await get_linked_volontario(update)
    if not volontario:
        return

    # Check if already clocked in
    open_entry = await Timbratura.objects.filter(
        fkvolontario=volontario,
        clock_out__isnull=True,
    ).afirst()

    if open_entry:
        await update.message.reply_text(
            f"⚠️ Hai già un'entrata aperta dalle {open_entry.clock_in:%H:%M del %d/%m/%Y}.\n\n"
            f"Usa /uscita per registrare l'uscita prima di una nuova entrata."
        )
        return

    # Create new time entry
    entry = await Timbratura.objects.acreate(volontario=volontario)

    await update.message.reply_text(
        f"✅ Entrata registrata alle {entry.clock_in:%H:%M}.\n\n"
        f"Buon lavoro! Usa /uscita quando hai finito."
    )


async def clock_out(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clock out - stop tracking time."""
    volontario = await get_linked_volontario(update)
    if not volontario:
        return

    # Find open entry
    open_entry = await Timbratura.objects.filter(
        fkvolontario=volontario,
        clock_out__isnull=True,
    ).afirst()

    if not open_entry:
        await update.message.reply_text(
            "❌ Non hai nessuna entrata aperta.\n\n"
            "Usa /entrata per registrare un'entrata."
        )
        return

    # Close the entry
    open_entry.clock_out = timezone.now()
    await open_entry.asave(update_fields=["clock_out"])

    # Calculate duration
    duration_minutes = open_entry.duration
    hours = int(duration_minutes // 60)
    minutes = int(duration_minutes % 60)

    await update.message.reply_text(
        f"✅ Uscita registrata alle {open_entry.clock_out:%H:%M}.\n\n"
        f"Durata: {hours}h {minutes}m\n"
        f"Grazie per il tuo servizio!"
    )


async def hours_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show hours summary for current month."""
    volontario = await get_linked_volontario(update)
    if not volontario:
        return

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get completed entries for this month
    entries = Timbratura.objects.filter(
        fkvolontario=volontario,
        clock_in__gte=month_start,
        clock_out__isnull=False,
    )

    total_minutes = 0
    entry_count = 0
    async for entry in entries:
        total_minutes += entry.duration or 0
        entry_count += 1

    # Check for open entry
    open_entry = await Timbratura.objects.filter(
       fkvolontario=volontario,
        clock_out__isnull=True,
    ).afirst()

    hours = int(total_minutes // 60)
    minutes = int(total_minutes % 60)

    month_name = now.strftime("%B %Y")
    message = (
        f"📊 Riepilogo ore - {month_name}\n\n"
        f"Totale: {hours}h {minutes}m\n"
        f"Sessioni completate: {entry_count}"
    )

    if open_entry:
        message += f"\n\n⏱️ Entrata in corso dalle {open_entry.clock_in:%H:%M}"

    await update.message.reply_text(message)


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a one-time login link for web access."""
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

    # Create a new login token
    token = await LoginToken.objects.acreate(telegram_user=tg_user)

    login_url = token.get_login_url()
    await update.message.reply_text(
        f"🔐 Ecco il tuo link di accesso:\n\n"
        f"{login_url}\n\n"
        f"⚠️ Il link è valido per 10 minuti e può essere usato una sola volta.",
    )


async def nuovo_servizio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the new service creation flow."""
    volontario = await get_linked_volontario(update)
    if not volontario:
        return ConversationHandler.END

    await update.message.reply_text(
        "📋 Creazione nuovo servizio\n\n"
        "Inserisci il nome del servizio:"
    )
    return ConversationState.WAITING_SERVIZIO_NAME.value


async def handle_servizio_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle service name input."""
    nome = update.message.text.strip()

    if len(nome) < 3:
        await update.message.reply_text(
            "❌ Il nome deve essere di almeno 3 caratteri.\n"
            "Riprova o usa /annulla per annullare."
        )
        return ConversationState.WAITING_SERVIZIO_NAME.value

    if len(nome) > 150:
        await update.message.reply_text(
            "❌ Il nome non può superare i 150 caratteri.\n"
            "Riprova o usa /annulla per annullare."
        )
        return ConversationState.WAITING_SERVIZIO_NAME.value

    context.user_data["servizio_nome"] = nome

    await update.message.reply_text(
        f"Nome: {nome}\n\n"
        "Inserisci la data del servizio (formato: GG/MM/AAAA):"
    )
    return ConversationState.WAITING_SERVIZIO_DATE.value


async def handle_servizio_date(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle service date input and create the service."""
    date_text = update.message.text.strip()

    # Parse date
    try:
        service_date = datetime.strptime(date_text, "%d/%m/%Y").date()
    except ValueError:
        await update.message.reply_text(
            "❌ Formato data non valido.\n"
            "Usa il formato GG/MM/AAAA (es. 25/01/2026).\n\n"
            "Riprova o usa /annulla per annullare."
        )
        return ConversationState.WAITING_SERVIZIO_DATE.value

    nome = context.user_data.get("servizio_nome")

    # Create the service
    servizio = await Servizio.objects.acreate(
        nome=nome,
        date=service_date,
    )

    await update.message.reply_text(
        f"✅ Servizio creato!\n\n"
        f"📌 {nome}\n"
        f"📅 {service_date:%d/%m/%Y}\n\n"
        f"Il sondaggio di disponibilità è stato inviato."
    )

    # Clean up user data
    context.user_data.pop("servizio_nome", None)

    return ConversationHandler.END


async def handle_poll_answer(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle poll answer from users."""
    answer = update.poll_answer
    user_id = answer.user.id
    poll_id = answer.poll_id
    option_ids = answer.option_ids

    # Get servizio from database by poll_id
    try:
        servizio = await Servizio.objects.aget(poll_id=poll_id)
    except Servizio.DoesNotExist:
        logger.debug(f"Poll {poll_id} not associated with any servizio, ignoring")
        return

    # Check if user is linked
    try:
        tg_user = await TelegramUser.objects.select_related("volontario").aget(
            telegram_id=user_id
        )
        if not tg_user.is_linked:
            logger.info(f"Unlinked user {user_id} answered poll {poll_id}")
            return
        volontario = tg_user.volontario
    except TelegramUser.DoesNotExist:
        logger.info(f"Unknown user {user_id} answered poll {poll_id}")
        return

    # Map option index to response
    response_map = {
        0: VolontarioServizioMap.Risposta.SI,
        1: VolontarioServizioMap.Risposta.NO,
        2: VolontarioServizioMap.Risposta.FORSE,
    }

    if option_ids:
        risposta = response_map.get(option_ids[0])
    else:
        # User retracted their vote
        risposta = None

    # Save or update the response
    await VolontarioServizioMap.objects.aupdate_or_create(
        fkvolontario=volontario,
        fkservizio=servizio,
        defaults={
            "risposta": risposta,
            "risposta_at": timezone.now() if risposta else None,
        },
    )

    logger.info(
        f"Poll answer: {volontario.nome} {volontario.cognome} "
        f"responded '{risposta}' for servizio {servizio.nome}"
    )


def create_application() -> Application:
    """Create and configure the bot application."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN non configurato in settings.py")

    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Conversation handler for /start and association flow
    start_conv_handler = ConversationHandler(
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

    # Conversation handler for /nuovoservizio
    servizio_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nuovoservizio", nuovo_servizio)],
        states={
            ConversationState.WAITING_SERVIZIO_NAME.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_servizio_name),
            ],
            ConversationState.WAITING_SERVIZIO_DATE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_servizio_date),
            ],
        },
        fallbacks=[
            CommandHandler("annulla", cancel),
            CommandHandler("cancel", cancel),
        ],
    )

    application.add_handler(start_conv_handler)
    application.add_handler(servizio_conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profilo", profile))
    application.add_handler(CommandHandler("entrata", clock_in))
    application.add_handler(CommandHandler("uscita", clock_out))
    application.add_handler(CommandHandler("ore", hours_summary))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(PollAnswerHandler(handle_poll_answer))

    return application


def run_bot() -> None:
    """Run the bot in polling mode."""
    application = create_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
