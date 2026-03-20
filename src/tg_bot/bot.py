import logging
from datetime import datetime, timedelta
from enum import Enum, auto

from django.utils import timezone
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PollAnswerHandler,
    filters,
)

from django.conf import settings
from django.contrib.auth import get_user_model

from .models import LoginToken, TelegramUser, WebLoginRequest
from servizio.models import (
    ChecklistItem,
    ScheduledTask,
    Servizio,
    ServizioType,
    Timbratura,
    VolontarioServizioMap,
)
from volontario.models import Volontario

User = get_user_model()

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    WAITING_CODICE_FISCALE = auto()
    WAITING_SERVIZIO_TYPE = auto()
    WAITING_SERVIZIO_NEW_TYPE = auto()
    WAITING_SERVIZIO_NAME = auto()
    WAITING_SERVIZIO_DATE = auto()
    WAITING_SERVIZIO_TIME = auto()
    WAITING_SERVIZIO_END_TIME = auto()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Handle the /start command."""
    user = update.effective_user
    if not user:
        return None

    # Get or create TelegramUser
    tg_user, created = await TelegramUser.objects.aget_or_create(
        telegram_id=user.id,
        defaults={
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
    )

    # Update user info if changed
    if not created:
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
    existing_link = (
        await TelegramUser.objects.filter(volontario=volontario)
        .exclude(telegram_id=user.id)
        .afirst()
    )

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
        "Operazione annullata.\nUsa /start per ricominciare."
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
            "❌ Non sei ancora registrato.\nUsa /start per associare il tuo account."
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
            "❌ Non sei ancora registrato.\nUsa /start per associare il tuo account."
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
            f"⚠️ Hai già un'entrata aperta dalle {timezone.localtime(open_entry.clock_in):%H:%M del %d/%m/%Y}.\n\n"
            f"Usa /uscita per registrare l'uscita prima di una nuova entrata."
        )
        return

    # Create new time entry
    entry = await Timbratura.objects.acreate(fkvolontario=volontario)

    clock_out_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔴 Registra uscita", callback_data="clock_out")]]
    )
    await update.message.reply_text(
        f"✅ Entrata registrata alle {timezone.localtime(entry.clock_in):%H:%M}.\n\n"
        f"Buon lavoro!",
        reply_markup=clock_out_keyboard,
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
        f"✅ Uscita registrata alle {timezone.localtime(open_entry.clock_out):%H:%M}.\n\n"
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

    month_name = timezone.localtime(now).strftime("%B %Y")
    message = (
        f"📊 Riepilogo ore - {month_name}\n\n"
        f"Totale: {hours}h {minutes}m\n"
        f"Sessioni completate: {entry_count}"
    )

    if open_entry:
        message += f"\n\n⏱️ Entrata in corso dalle {timezone.localtime(open_entry.clock_in):%H:%M}"

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
            "❌ Non sei ancora registrato.\nUsa /start per associare il tuo account."
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
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )



async def nuovo_servizio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the new service creation flow."""
    volontario = await get_linked_volontario(update)
    if not volontario:
        return ConversationHandler.END

    # Build inline keyboard with existing types + "Nuovo tipo"
    types = []
    async for st in ServizioType.objects.all().order_by("nome"):
        types.append(st)

    buttons = [
        [InlineKeyboardButton(st.nome, callback_data=f"stype:{st.pkid}")]
        for st in types
    ]
    buttons.append(
        [InlineKeyboardButton("➕ Nuovo tipo", callback_data="stype:new")]
    )

    await update.message.reply_text(
        "📋 Creazione nuovo servizio\n\nSeleziona il tipo di servizio:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return ConversationState.WAITING_SERVIZIO_TYPE.value


async def handle_servizio_type_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle service type selection from inline keyboard."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("stype:"):
        return ConversationState.WAITING_SERVIZIO_TYPE.value

    choice = data.split(":", 1)[1]

    if choice == "new":
        await query.edit_message_text(
            "📋 Creazione nuovo servizio\n\n"
            "Inserisci il nome del nuovo tipo di servizio:"
        )
        return ConversationState.WAITING_SERVIZIO_NEW_TYPE.value

    # Existing type selected
    try:
        servizio_type = await ServizioType.objects.aget(pkid=choice)
    except ServizioType.DoesNotExist:
        await query.edit_message_text("❌ Tipo non trovato. Riprova con /nuovoservizio.")
        return ConversationHandler.END

    context.user_data["servizio_type_id"] = str(servizio_type.pkid)
    await query.edit_message_text(
        f"Tipo: {servizio_type.nome}\n\nInserisci il nome del servizio:"
    )
    return ConversationState.WAITING_SERVIZIO_NAME.value


async def handle_servizio_new_type(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle new service type name input."""
    nome = update.message.text.strip()

    if len(nome) < 2:
        await update.message.reply_text(
            "❌ Il nome del tipo deve essere di almeno 2 caratteri.\n"
            "Riprova o usa /annulla per annullare."
        )
        return ConversationState.WAITING_SERVIZIO_NEW_TYPE.value

    if len(nome) > 150:
        await update.message.reply_text(
            "❌ Il nome del tipo non può superare i 150 caratteri.\n"
            "Riprova o usa /annulla per annullare."
        )
        return ConversationState.WAITING_SERVIZIO_NEW_TYPE.value

    servizio_type, created = await ServizioType.objects.aget_or_create(nome=nome)
    context.user_data["servizio_type_id"] = str(servizio_type.pkid)

    label = "Nuovo tipo creato" if created else "Tipo esistente selezionato"
    await update.message.reply_text(
        f"{label}: {servizio_type.nome}\n\nInserisci il nome del servizio:"
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
        f"Nome: {nome}\n\nInserisci la data del servizio (formato: GG/MM/AAAA):"
    )
    return ConversationState.WAITING_SERVIZIO_DATE.value


async def handle_servizio_date(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle service date input."""
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

    context.user_data["servizio_date"] = service_date

    await update.message.reply_text(
        f"Data: {service_date:%d/%m/%Y}\n\n"
        "Inserisci l'ora del servizio (formato: HH:MM):"
    )
    return ConversationState.WAITING_SERVIZIO_TIME.value


async def handle_servizio_time(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle service start time input."""
    time_text = update.message.text.strip()

    try:
        service_time = datetime.strptime(time_text, "%H:%M").time()
    except ValueError:
        await update.message.reply_text(
            "❌ Formato ora non valido.\n"
            "Usa il formato HH:MM (es. 14:30).\n\n"
            "Riprova o usa /annulla per annullare."
        )
        return ConversationState.WAITING_SERVIZIO_TIME.value

    service_date = context.user_data.get("servizio_date")
    service_datetime = timezone.make_aware(datetime.combine(service_date, service_time))
    context.user_data["servizio_datetime"] = service_datetime

    await update.message.reply_text(
        f"Inizio: {service_datetime:%d/%m/%Y %H:%M}\n\n"
        "Inserisci l'ora di fine (formato: HH:MM) o /salta per non specificarla:"
    )
    return ConversationState.WAITING_SERVIZIO_END_TIME.value


async def handle_servizio_end_time(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle service end time input and create the service."""
    time_text = update.message.text.strip()

    try:
        end_time = datetime.strptime(time_text, "%H:%M").time()
    except ValueError:
        await update.message.reply_text(
            "❌ Formato ora non valido.\n"
            "Usa il formato HH:MM (es. 18:00) o /salta per non specificarla.\n\n"
            "Riprova o usa /annulla per annullare."
        )
        return ConversationState.WAITING_SERVIZIO_END_TIME.value

    service_datetime = context.user_data.get("servizio_datetime")
    # If end time is earlier than start, assume it falls on the next day
    end_date = service_datetime.date()
    if end_time <= service_datetime.time():
        from datetime import timedelta
        end_date = end_date + timedelta(days=1)
    end_datetime = timezone.make_aware(datetime.combine(end_date, end_time))
    context.user_data["servizio_end_datetime"] = end_datetime

    return await _create_servizio(update, context)


async def _skip_servizio_end_time(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle /salta command to skip end time."""
    context.user_data["servizio_end_datetime"] = None
    return await _create_servizio(update, context)


async def _create_servizio(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Create the Servizio and send confirmation."""
    nome = context.user_data.get("servizio_nome")
    service_datetime = context.user_data.get("servizio_datetime")
    end_datetime = context.user_data.get("servizio_end_datetime")
    type_id = context.user_data.get("servizio_type_id")

    servizio_type = None
    if type_id:
        try:
            servizio_type = await ServizioType.objects.aget(pkid=type_id)
        except ServizioType.DoesNotExist:
            pass

    await Servizio.objects.acreate(
        nome=nome,
        data_ora=service_datetime,
        data_ora_fine=end_datetime,
        type=servizio_type,
    )

    type_line = f"📂 {servizio_type.nome}\n" if servizio_type else ""
    end_line = f"🏁 Fine: {end_datetime:%d/%m/%Y %H:%M}\n" if end_datetime else ""
    await update.message.reply_text(
        f"✅ Servizio creato!\n\n"
        f"📌 {nome}\n"
        f"{type_line}"
        f"📅 Inizio: {service_datetime:%d/%m/%Y %H:%M}\n"
        f"{end_line}\n"
        f"Il sondaggio di disponibilità è stato inviato."
    )

    context.user_data.pop("servizio_nome", None)
    context.user_data.pop("servizio_date", None)
    context.user_data.pop("servizio_type_id", None)
    context.user_data.pop("servizio_datetime", None)
    context.user_data.pop("servizio_end_datetime", None)

    return ConversationHandler.END


async def handle_web_login_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle web login approval/denial callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("web_login:"):
        return

    parts = data.split(":")
    if len(parts) != 3:
        return

    _, action, token = parts

    # Get the login request
    try:
        login_request = await WebLoginRequest.objects.aget(token=token)
    except WebLoginRequest.DoesNotExist:
        await query.edit_message_text("❌ Richiesta non trovata o già elaborata.")
        return

    # Check if already processed
    if login_request.status != WebLoginRequest.Status.PENDING:
        status_text = login_request.get_status_display()
        await query.edit_message_text(
            f"Questa richiesta è già stata elaborata: {status_text}"
        )
        return

    # Check if expired
    if not login_request.is_pending:
        login_request.status = WebLoginRequest.Status.EXPIRED
        await login_request.asave(update_fields=["status"])
        await query.edit_message_text("⏱️ Richiesta scaduta.")
        return

    # Fetch volontario details separately for async context
    volontario_data = (
        await WebLoginRequest.objects.filter(token=token)
        .values("volontario__nome", "volontario__cognome")
        .afirst()
    )
    volontario_nome = volontario_data["volontario__nome"]
    volontario_cognome = volontario_data["volontario__cognome"]

    # Process the action
    if action == "approve":
        login_request.status = WebLoginRequest.Status.APPROVED
        login_request.resolved_at = timezone.now()
        await login_request.asave(update_fields=["status", "resolved_at"])
        await query.edit_message_text(
            f"✅ Accesso approvato per {volontario_nome} {volontario_cognome}.\n\n"
            "La sessione web è ora attiva."
        )
    elif action == "deny":
        login_request.status = WebLoginRequest.Status.DENIED
        login_request.resolved_at = timezone.now()
        await login_request.asave(update_fields=["status", "resolved_at"])
        await query.edit_message_text(
            "❌ Accesso rifiutato.\n\n"
            "Se non hai richiesto tu l'accesso, qualcuno potrebbe aver tentato "
            "di accedere con il tuo codice fiscale."
        )


async def handle_clock_in_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle clock-in button press from reminder notification."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("clock_in:"):
        return

    servizio_pkid = data.split(":", 1)[1]

    # Get linked volontario
    user_id = query.from_user.id
    try:
        tg_user = await TelegramUser.objects.aget(telegram_id=user_id)
    except TelegramUser.DoesNotExist:
        await query.edit_message_text(
            "❌ Non sei registrato. Usa /start per associare il tuo account."
        )
        return

    if not tg_user.is_linked:
        await query.edit_message_text(
            "❌ Il tuo account non è associato. Usa /start per completare l'associazione."
        )
        return

    volontario = await Volontario.objects.aget(pk=tg_user.volontario_id)

    # Get the servizio
    try:
        servizio = await Servizio.objects.aget(pkid=servizio_pkid)
    except Servizio.DoesNotExist:
        await query.edit_message_text("❌ Servizio non trovato.")
        return

    # Check if already clocked in (for any servizio)
    open_entry = await Timbratura.objects.filter(
        fkvolontario=volontario,
        clock_out__isnull=True,
    ).afirst()

    if open_entry:
        await query.edit_message_text(
            f"⚠️ Hai già un'entrata aperta dalle {timezone.localtime(open_entry.clock_in):%H:%M del %d/%m/%Y}.\n\n"
            f"Usa /uscita per registrare l'uscita prima di una nuova entrata."
        )
        return

    # Create new time entry linked to the servizio
    entry = await Timbratura.objects.acreate(
        fkvolontario=volontario,
        fkservizio=servizio,
    )

    clock_out_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔴 Registra uscita", callback_data="clock_out")]]
    )
    await query.edit_message_text(
        f'✅ Entrata registrata alle {timezone.localtime(entry.clock_in):%H:%M} per il servizio "{servizio.nome}".\n\n'
        f"Buon lavoro!",
        reply_markup=clock_out_keyboard,
    )
    logger.info(f"Clock-in via button: {volontario.nome} for servizio {servizio.nome}")


async def handle_clock_out_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle clock-out button press."""
    query = update.callback_query

    user_id = query.from_user.id
    try:
        tg_user = await TelegramUser.objects.aget(telegram_id=user_id)
    except TelegramUser.DoesNotExist:
        await query.answer("Non sei registrato. Usa /start.", show_alert=True)
        return
    if not tg_user.is_linked:
        await query.answer("Account non associato. Usa /start.", show_alert=True)
        return
    volontario = await Volontario.objects.aget(pk=tg_user.volontario_id)

    open_entry = await Timbratura.objects.filter(
        fkvolontario=volontario,
        clock_out__isnull=True,
    ).afirst()

    if not open_entry:
        await query.answer("Nessuna entrata aperta.", show_alert=True)
        return

    open_entry.clock_out = timezone.now()
    await open_entry.asave(update_fields=["clock_out"])

    duration_minutes = open_entry.duration
    hours = int(duration_minutes // 60)
    minutes = int(duration_minutes % 60)

    await query.edit_message_text(
        f"✅ Uscita registrata alle {timezone.localtime(open_entry.clock_out):%H:%M}.\n\n"
        f"Durata: {hours}h {minutes}m\n"
        f"Grazie per il tuo servizio!"
    )
    logger.info(f"Clock-out via button: {volontario.nome}")


async def close_expired_polls(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Close polls for servizi starting within 12 hours."""
    now = timezone.now()
    cutoff = now + timedelta(hours=12)

    # Find servizi with open polls that start within 24 hours
    servizi_to_close = Servizio.objects.filter(
        data_ora__lte=cutoff,
        poll_message_id__isnull=False,
        poll_closed=False,
    )

    chat_id = getattr(settings, "TELEGRAM_SURVEY_CHAT_ID", None)
    if not chat_id:
        return

    async for servizio in servizi_to_close:
        if not servizio.poll_message_id:
            continue
        try:
            await context.bot.stop_poll(
                chat_id=chat_id,
                message_id=servizio.poll_message_id,
            )
            logger.info(f"Closed poll for servizio {servizio.pkid} ({servizio.nome})")
        except Exception as e:
            logger.error(
                f"Failed to close poll for servizio {servizio.pkid}: {e}"
            )
        servizio.poll_closed = True
        await servizio.asave(update_fields=["poll_closed"])


async def send_servizio_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check for upcoming servizi and send reminders to volunteers."""
    now = timezone.now()
    reminder_window_start = now + timedelta(minutes=25)
    reminder_window_end = now + timedelta(minutes=31)

    # Find servizi starting in ~10 minutes that haven't been notified yet
    upcoming_servizi = Servizio.objects.filter(
        data_ora__gte=reminder_window_start,
        data_ora__lte=reminder_window_end,
        notification_sent=False,
    )

    async for servizio in upcoming_servizi:
        # Get all volunteers associated with this servizio (those who responded)

        participants = servizio.volontarioserviziomap_set.exclude(
            risposta=VolontarioServizioMap.Risposta.NO,
        ).select_related("fkvolontario")

        async for answer in participants:
            volontario = answer.fkvolontario
            # Get the telegram user for this volontario
            try:
                tg_user = await TelegramUser.objects.aget(volontario=volontario)
            except TelegramUser.DoesNotExist:
                logger.debug(f"No telegram user for volontario {volontario.pkid}")
                continue

            # Send personal reminder with inline button
            risposta_text = (
                answer.get_risposta_display() if answer.risposta else "non data"
            )
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Registra entrata",
                            callback_data=f"clock_in:{servizio.pkid}",
                        )
                    ]
                ]
            )
            end_line = ""
            if servizio.data_ora_fine:
                end_line = f"🏁 Fine: {timezone.localtime(servizio.data_ora_fine):%d/%m/%Y %H:%M}\n"
            try:
                await context.bot.send_message(
                    chat_id=tg_user.telegram_id,
                    text=(
                        f"⏰ Promemoria!\n\n"
                        f'Il servizio "{servizio.nome}" inizia tra 30 minuti.\n'
                        f"📅 Inizio: {timezone.localtime(servizio.data_ora):%d/%m/%Y %H:%M}\n"
                        f"{end_line}"
                        f"\nLa tua risposta: {risposta_text}"
                    ),
                    reply_markup=keyboard,
                )
                logger.info(
                    f"Sent reminder to {volontario.nome} for servizio {servizio.nome}"
                )
            except Exception as e:
                logger.error(f"Failed to send reminder to {tg_user.telegram_id}: {e}")

        # Mark servizio as notified
        servizio.notification_sent = True
        await servizio.asave(update_fields=["notification_sent"])
        logger.info(f"Marked servizio {servizio.pkid} as notified")


async def send_clock_out_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send clock-out reminders to volunteers still clocked in when a servizio ends."""
    now = timezone.now()
    window_start = now - timedelta(seconds=65)

    # Find servizi whose end time just passed and haven't had the reminder sent yet
    ended_servizi = Servizio.objects.filter(
        data_ora_fine__isnull=False,
        data_ora_fine__gte=window_start,
        data_ora_fine__lte=now,
        end_reminder_sent=False,
    )

    async for servizio in ended_servizi:
        # Find volunteers still clocked in for this servizio
        open_entries = Timbratura.objects.filter(
            fkservizio=servizio,
            clock_out__isnull=True,
        ).select_related("fkvolontario")

        async for entry in open_entries:
            volontario = entry.fkvolontario
            try:
                tg_user = await TelegramUser.objects.aget(volontario=volontario)
            except TelegramUser.DoesNotExist:
                logger.debug(f"No telegram user for volontario {volontario.pkid}")
                continue

            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔴 Registra uscita", callback_data="clock_out")]]
            )
            try:
                await context.bot.send_message(
                    chat_id=tg_user.telegram_id,
                    text=(
                        f"⏰ Il servizio \"{servizio.nome}\" è terminato.\n\n"
                        f"Ricordati di registrare l'uscita!"
                    ),
                    reply_markup=keyboard,
                )
                logger.info(
                    f"Sent clock-out reminder to {volontario.nome} for servizio {servizio.nome}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to send clock-out reminder to {tg_user.telegram_id}: {e}"
                )

        servizio.end_reminder_sent = True
        await servizio.asave(update_fields=["end_reminder_sent"])
        logger.info(f"Marked servizio {servizio.pkid} end_reminder_sent")


async def enforce_locked_topic(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete any message posted in a locked topic by someone other than the bot."""
    message = update.effective_message
    if not message:
        return

    locked_ids = getattr(settings, "TELEGRAM_LOCKED_THREAD_IDS", [])
    if message.message_thread_id not in locked_ids:
        return

    # Leave the bot's own messages (polls, notifications) untouched
    if message.from_user and message.from_user.id == context.bot.id:
        return

    try:
        await message.delete()
        logger.info(
            f"Deleted message {message.message_id} in locked topic {message.message_thread_id} "
            f"from user {message.from_user and message.from_user.id}"
        )
    except Exception as e:
        logger.warning(f"Could not delete message {message.message_id}: {e}")
        return

    if message.from_user:
        try:
            await context.bot.send_message(
                chat_id=message.from_user.id,
                text="🚫 Il tuo messaggio è stato eliminato perché questo topic è riservato e non accetta messaggi.",
            )
        except Exception as e:
            logger.warning(f"Could not DM user {message.from_user.id} after message deletion: {e}")


async def handle_topic_reopened(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Re-close a forum topic that should stay closed."""
    message = update.effective_message
    if not message:
        return

    locked_ids = getattr(settings, "TELEGRAM_LOCKED_THREAD_IDS", [])
    if message.message_thread_id not in locked_ids:
        return

    try:
        await context.bot.close_forum_topic(
            chat_id=message.chat_id,
            message_thread_id=message.message_thread_id,
        )
        logger.info(f"Re-closed topic {message.message_thread_id} in chat {message.chat_id}")
    except Exception as e:
        logger.warning(f"Could not re-close topic {message.message_thread_id}: {e}")


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


async def greet_new_member(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Greet new members joining the chat and prompt them to enable the bot."""
    for member in update.message.new_chat_members:
        # Skip if the bot itself joined
        if member.id == context.bot.id:
            continue

        # Save telegram user to database for potential manual activation later
        tg_user, created = await TelegramUser.objects.aget_or_create(
            telegram_id=member.id,
            defaults={
                "username": member.username,
                "first_name": member.first_name,
                "last_name": member.last_name,
            },
        )

        if not created:
            # Update info if user already existed
            tg_user.username = member.username
            tg_user.first_name = member.first_name
            tg_user.last_name = member.last_name
            await tg_user.asave()

        logger.info(
            f"New member joined: {member.first_name} (@{member.username}) - "
            f"TelegramUser {'created' if created else 'updated'}"
        )

        await update.message.reply_text(
            f"Ciao {member.first_name}! 👋\n\n"
            f"Per utilizzare il bot e accedere a tutte le funzionalità, "
            f"avvia una chat privata con me per "
            f"associare il tuo account Telegram al tuo profilo volontario."
        )


async def _build_checklist_message(task: ScheduledTask) -> tuple[str, InlineKeyboardMarkup | None]:
    """Build checklist message text and keyboard for a ScheduledTask."""
    completed_lines = []
    pending_buttons = []

    async for item in ChecklistItem.objects.filter(
        scheduled_task=task
    ).select_related("completato_da").order_by("ordine"):
        if item.completato:
            nome = item.completato_da.nome if item.completato_da else "?"
            ora = timezone.localtime(item.completato_at).strftime("%H:%M") if item.completato_at else ""
            completed_lines.append(f"✅ {item.descrizione} - {nome} ({ora})")
        else:
            pending_buttons.append([
                InlineKeyboardButton(
                    item.descrizione,
                    callback_data=f"chk:{item.pkid}",
                )
            ])

    text = f"Checklist: {task.nome}\n"
    if completed_lines:
        text += "\n" + "\n".join(completed_lines)

    keyboard = InlineKeyboardMarkup(pending_buttons) if pending_buttons else None
    return text, keyboard


async def _send_checklist_message(bot, chat_id: int, task: ScheduledTask) -> int:
    """Send a checklist message with inline buttons to a chat. Returns message_id."""
    text, keyboard = await _build_checklist_message(task)
    msg = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
    )
    return msg.message_id


async def _handle_task_completion(bot, task: ScheduledTask) -> None:
    """Handle completion of all checklist items."""
    task.completed = True
    task.completed_at = timezone.now()
    await task.asave(update_fields=["completed", "completed_at"])

    # Close all open timbrature for this task
    now = timezone.now()
    async for t in Timbratura.objects.filter(
        fkscheduled_task=task, clock_out__isnull=True
    ):
        t.clock_out = now
        await t.asave(update_fields=["clock_out"])

    # Notify staff users
    staff_tg_users = TelegramUser.objects.filter(
        volontario__user__is_staff=True,
        volontario__isnull=False,
    )
    async for tg_user in staff_tg_users:
        try:
            await bot.send_message(
                chat_id=tg_user.telegram_id,
                text=(
                    f"Attivita completata!\n\n"
                    f"{task.nome}\n"
                    f"Tutti gli elementi della checklist sono stati completati.\n"
                    f"Le timbrature aperte sono state chiuse automaticamente."
                ),
            )
        except Exception as e:
            logger.error(f"Failed to notify staff {tg_user.telegram_id}: {e}")


async def send_scheduled_task_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send reminders 48h before ScheduledTask deadline."""
    now = timezone.now()
    window_start = now + timedelta(hours=47, minutes=55)
    window_end = now + timedelta(hours=48, minutes=5)

    tasks = ScheduledTask.objects.filter(
        deadline__gte=window_start,
        deadline__lte=window_end,
        notification_sent=False,
        completed=False,
    )

    async for task in tasks:
        async for volontario in task.volontari.all():
            try:
                tg_user = await TelegramUser.objects.aget(volontario=volontario)
            except TelegramUser.DoesNotExist:
                continue

            # Build a plain-text preview of checklist items
            checklist_lines = []
            async for item in ChecklistItem.objects.filter(
                scheduled_task=task
            ).order_by("ordine"):
                checklist_lines.append(f"- {item.descrizione}")
            checklist_text = "\n".join(checklist_lines)

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "Inizia Timbratura",
                    callback_data=f"task_start:{task.pkid}",
                )]
            ])

            try:
                await context.bot.send_message(
                    chat_id=tg_user.telegram_id,
                    text=(
                        f"Attivita programmata in scadenza!\n\n"
                        f"{task.nome}\n"
                        f"Scadenza: {timezone.localtime(task.deadline):%d/%m/%Y %H:%M}\n\n"
                        f"Checklist:\n{checklist_text}\n\n"
                        f"Premi il pulsante per registrare la tua entrata."
                    ),
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.error(
                    f"Failed to send task reminder to {tg_user.telegram_id}: {e}"
                )

        task.notification_sent = True
        await task.asave(update_fields=["notification_sent"])
        logger.info(f"Sent reminders for scheduled task {task.pkid} ({task.nome})")


async def handle_task_start_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle clock-in for a scheduled task."""
    query = update.callback_query
    chat_id = query.message.chat_id

    task_pkid = query.data.split(":", 1)[1]

    # Resolve volontario
    user_id = query.from_user.id
    try:
        tg_user = await TelegramUser.objects.aget(telegram_id=user_id)
    except TelegramUser.DoesNotExist:
        await query.answer("Non sei registrato. Usa /start.", show_alert=True)
        return
    if not tg_user.is_linked:
        await query.answer("Account non associato. Usa /start.", show_alert=True)
        return
    volontario = await Volontario.objects.aget(pk=tg_user.volontario_id)

    # Get task
    try:
        task = await ScheduledTask.objects.aget(pkid=task_pkid)
    except ScheduledTask.DoesNotExist:
        await query.answer("Attivita non trovata.", show_alert=True)
        return

    # Verify assignment
    is_assigned = await task.volontari.filter(pk=volontario.pk).aexists()
    if not is_assigned:
        await query.answer("Non sei assegnato a questa attivita.", show_alert=True)
        return

    # Check for existing timbratura for this task
    existing_entry = await Timbratura.objects.filter(
        fkvolontario=volontario, fkscheduled_task=task
    ).afirst()
    if existing_entry:
        await query.answer("Hai gia registrato l'entrata per questa attivita.", show_alert=True)
        return

    # Check for open timbratura
    open_entry = await Timbratura.objects.filter(
        fkvolontario=volontario, clock_out__isnull=True
    ).afirst()
    if open_entry:
        await query.answer(
            f"Hai gia un'entrata aperta dalle {timezone.localtime(open_entry.clock_in):%H:%M del %d/%m/%Y}.\n"
            f"Usa /uscita prima di iniziare.",
            show_alert=True,
        )
        return

    # Create timbratura linked to scheduled task
    entry = await Timbratura.objects.acreate(
        fkvolontario=volontario, fkscheduled_task=task
    )

    await query.answer()

    # Delete the reminder message with the inline button
    try:
        await query.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Entrata registrata alle {timezone.localtime(entry.clock_in):%H:%M} per \"{task.nome}\".",
    )

    # Send checklist message and store its ID on the timbratura
    msg_id = await _send_checklist_message(context.bot, chat_id, task)
    entry.checklist_message_id = msg_id
    await entry.asave(update_fields=["checklist_message_id"])
    logger.info(f"Clock-in via task button: {volontario.nome} for task {task.nome}")


async def handle_checklist_toggle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle toggling a checklist item."""
    query = update.callback_query
    await query.answer()

    item_pkid = query.data.split(":", 1)[1]

    # Resolve volontario
    user_id = query.from_user.id
    try:
        tg_user = await TelegramUser.objects.aget(telegram_id=user_id)
    except TelegramUser.DoesNotExist:
        return
    if not tg_user.is_linked:
        return
    volontario = await Volontario.objects.aget(pk=tg_user.volontario_id)

    # Get checklist item
    try:
        item = await ChecklistItem.objects.select_related("scheduled_task").aget(
            pkid=item_pkid
        )
    except ChecklistItem.DoesNotExist:
        return

    task = item.scheduled_task

    # Verify assignment
    is_assigned = await task.volontari.filter(pk=volontario.pk).aexists()
    if not is_assigned:
        return

    # Mark as complete
    item.completato = True
    item.completato_da = volontario
    item.completato_at = timezone.now()
    await item.asave(update_fields=["completato", "completato_da", "completato_at"])

    # Rebuild checklist and update ALL tracked messages for this task
    text, keyboard = await _build_checklist_message(task)
    async for entry in Timbratura.objects.filter(
        fkscheduled_task=task, checklist_message_id__isnull=False
    ).select_related("fkvolontario"):
        try:
            tg_user = await TelegramUser.objects.aget(
                volontario=entry.fkvolontario
            )
        except TelegramUser.DoesNotExist:
            continue
        try:
            await context.bot.edit_message_text(
                chat_id=tg_user.telegram_id,
                message_id=entry.checklist_message_id,
                text=text,
                reply_markup=keyboard,
            )
        except Exception:
            pass  # Message unchanged or deleted

    # Check if all items are now complete
    remaining = await ChecklistItem.objects.filter(
        scheduled_task=task, completato=False
    ).acount()

    if remaining == 0 and not task.completed:
        await _handle_task_completion(context.bot, task)


async def post_init(application: Application) -> None:
    """Register bot commands in the Telegram menu."""
    commands = [
        BotCommand("start", "Avvia il bot"),
        BotCommand("help", "Mostra i comandi disponibili"),
        BotCommand("profilo", "Visualizza il tuo profilo"),
        BotCommand("entrata", "Registra entrata"),
        BotCommand("uscita", "Registra uscita"),
        BotCommand("ore", "Riepilogo ore del mese"),
        BotCommand("nuovoservizio", "Crea un nuovo servizio"),
        BotCommand("login", "Ottieni link di accesso al sito"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered")


def create_application() -> Application:
    """Create and configure the bot application."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN non configurato in settings.py")

    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Schedule jobs
    job_queue = application.job_queue
    job_queue.run_repeating(send_servizio_reminders, interval=60, first=10)
    job_queue.run_repeating(close_expired_polls, interval=300, first=15)
    job_queue.run_repeating(send_scheduled_task_reminders, interval=60, first=20)
    job_queue.run_repeating(send_clock_out_reminders, interval=60, first=30)

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
        per_message=False,  # One conversation per user at a time, no need for per-message tracking
        states={
            ConversationState.WAITING_SERVIZIO_TYPE.value: [
                CallbackQueryHandler(
                    handle_servizio_type_callback, pattern=r"^stype:"
                ),
            ],
            ConversationState.WAITING_SERVIZIO_NEW_TYPE.value: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_servizio_new_type
                ),
            ],
            ConversationState.WAITING_SERVIZIO_NAME.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_servizio_name),
            ],
            ConversationState.WAITING_SERVIZIO_DATE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_servizio_date),
            ],
            ConversationState.WAITING_SERVIZIO_TIME.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_servizio_time),
            ],
            ConversationState.WAITING_SERVIZIO_END_TIME.value: [
                CommandHandler("salta", _skip_servizio_end_time),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_servizio_end_time),
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
    application.add_handler(
        CallbackQueryHandler(handle_web_login_callback, pattern=r"^web_login:")
    )
    application.add_handler(
        CallbackQueryHandler(handle_clock_in_callback, pattern=r"^clock_in:")
    )
    application.add_handler(
        CallbackQueryHandler(handle_clock_out_callback, pattern=r"^clock_out$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_task_start_callback, pattern=r"^task_start:")
    )
    application.add_handler(
        CallbackQueryHandler(handle_checklist_toggle_callback, pattern=r"^chk:")
    )
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, greet_new_member)
    )

    # Locked topic enforcement (group=-1 so it runs before all other handlers)
    application.add_handler(
        MessageHandler(filters.ALL, enforce_locked_topic), group=-1
    )
    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.FORUM_TOPIC_REOPENED, handle_topic_reopened
        ),
        group=-1,
    )

    return application


def run_bot() -> None:
    """Run the bot in polling mode."""
    application = create_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
