from django.conf import settings
from django.contrib.auth.models import Group, User
from django.utils import timezone
from django_tgbot.decorators import processor
from django_tgbot.state_manager import state_types, update_types, message_types
from django_tgbot.types.inlinekeyboardbutton import InlineKeyboardButton
from django_tgbot.types.inlinekeyboardmarkup import InlineKeyboardMarkup
from django_tgbot.types.replykeyboardmarkup import ReplyKeyboardMarkup
from django_tgbot.types.keyboardbutton import KeyboardButton
from django_tgbot.types.update import Update
from django_tgbot.exceptions import ProcessFailure
from django.core.exceptions import ObjectDoesNotExist
from core.models import Profile
from servizio.models import Servizio, ServizioResponse, Timbratura
from warehouse.models import Loan
import json
from datetime import datetime as dt
from enum import StrEnum

from .bot import TelegramBot, state_manager
from .models import TelegramState, TelegramUser

MAIN_KEYBOARD = ReplyKeyboardMarkup.a(
    keyboard=[
        [
            KeyboardButton.a(text="Timbratura"),
        ]
    ]
)


class StateEnum(StrEnum):
    MAIN = "main"
    REGISTRATION_STEP1 = "registration_step1"
    DISABLED = "disabled"


def set_main_keyboard(bot: TelegramBot, user: TelegramUser):
    bot.sendMessage(
        chat_id=user.telegram_id,
        reply_markup=MAIN_KEYBOARD,
    )


@processor(
    state_manager,
    from_states=state_types.Reset,
    message_types=message_types.Text,
    success=StateEnum.REGISTRATION_STEP1,
)
def register(bot: TelegramBot, update: Update, state: TelegramState):
    if getattr(update.get_message(), "text", None) != "/start":
        return

    userid = update.get_user().get_id()
    tguser = TelegramUser.objects.get(telegram_id=userid)

    try:
        currentuser = tguser.profile.fkuser  # noqa
    except TelegramUser.profile.RelatedObjectDoesNotExist:
        # bot.sendMessage(
        #     update.get_chat().get_id(),
        #     f"Vai su {settings.OUTSIDE_URL}/hr/link_tg/"
        #     f"{str(new_verification_token.security_code)} entro 10 minuti"
        #     f" per collegare il tuo account",
        # )
        bot.sendMessage(
            update.get_chat().get_id(),
            "Benvenuto! Premi il pulsante 'Registrati' qui sotto per registrarti, poi clicca 'Condividi Contatto'",
            reply_markup=ReplyKeyboardMarkup.a(
                keyboard=[
                    [
                        KeyboardButton.a(text="Registrati", request_contact=True),
                    ]
                ]
            ),
        )
        # set_main_keyboard(bot, update.get_user().get_id())
    else:
        bot.sendMessage(
            update.get_chat().get_id(), "Sei già registrato", reply_markup=MAIN_KEYBOARD
        )


@processor(
    state_manager,
    message_types=[
        message_types.Contact,
    ],
    update_types=[],
    from_states=[StateEnum.REGISTRATION_STEP1],
    success=StateEnum.MAIN,
)
def associate_contact_to_user(bot: TelegramBot, update: Update, state: TelegramState):
    contact = update.message.obj["contact"]

    try:
        # When sending from mobile, number does not start with +
        if not contact["phone_number"].startswith("+"):
            contact["phone_number"] = "+" + contact["phone_number"]

        userprofile = Profile.objects.get(phone_number=contact["phone_number"])

    except ObjectDoesNotExist as e:
        bot.sendMessage(update.get_chat().get_id(), "Utente non trovato")
        raise ProcessFailure from e

    tguser = TelegramUser.objects.get(telegram_id=update.get_user().get_id())

    userprofile.telegram_user = tguser
    userprofile.save()

    bot.sendMessage(
        chat_id=update.get_chat().get_id(),
        reply_markup=MAIN_KEYBOARD,
        text="Registrazione riuscita",
    )


@processor(
    state_manager,
    from_states=[StateEnum.MAIN],
    message_types=message_types.Text,
)
def timbra_inizio(bot: TelegramBot, update: Update, state: TelegramState):
    if getattr(update.get_message(), "text", None) != "Timbratura":
        return

    userid = update.get_user().get_id()
    tguser = TelegramUser.objects.get(telegram_id=userid)
    currentuser = tguser.profile.fkuser  # noqa
    servizio = Servizio.objects.first()
    timbratura = Timbratura.objects.create(
        fkservizio=servizio,
        fkuser=currentuser,
        message_id=update.get_message().get_message_id(),
    )

    bot.sendMessage(
        update.get_chat().get_id(),
        f"Timbrato inizio attività alle {timbratura.datetime_begin}",
        reply_markup=InlineKeyboardMarkup.a(
            inline_keyboard=[
                [
                    InlineKeyboardButton.a(
                        text="Timbra fine servizio",
                        callback_data=json.dumps(
                            {
                                "message_type": "timbratura",
                                "action": "end",
                                "data": timbratura.id,
                            }
                        ),
                    )
                ]
            ]
        ),
    )


@processor(
    state_manager, update_types=update_types.CallbackQuery, from_states=state_types.All
)
def timbra_fine(bot: TelegramBot, update: Update, state: TelegramState):
    data = json.loads(update.get_callback_query().get_data())
    if data["message_type"] != "timbratura":
        return

    timbratura = Timbratura.objects.get(id=data["data"])
    if timbratura.datetime_end is not None:
        return

    timbratura.datetime_end = dt.now()
    timbratura.save()

    bot.editMessageText(
        text=f"{update.get_callback_query().get_message().get_text()}\n\n"
        f"Timbrata fine alle {timbratura.datetime_end}",
        message_id=update.get_callback_query().get_message().get_message_id(),
        chat_id=update.get_callback_query().get_chat().get_id(),
    )


def nuovo_servizio_callback(bot: TelegramBot, instance: Servizio) -> int:
    poll = bot.sendPoll(
        settings.GROUP_CHAT_ID,
        question=f"Nuovo servizio il {instance.begin_date}.\n Confermi dispobilità?",
        options=["Sì", "Forse", "No"],
        is_anonymous=False,
        close_date=instance.begin_date,
    )

    return poll.poll.id


def new_item_loaned_to_user(bot: TelegramBot, tg_user: TelegramUser, instance: Loan):
    msg = bot.sendMessage(
        tg_user.telegram_id,
        f"{instance.fkinventory_item.brand} {instance.fkinventory_item.model} assegnata a te\n\n"
        "Premi qui per riconsegnare",
        reply_markup=InlineKeyboardMarkup.a(
            inline_keyboard=[
                [InlineKeyboardButton.a(text="Riconsegna", callback_data="item_return")]
            ]
        ),
    )

    return msg


@processor(
    state_manager,
    update_types=[update_types.CallbackQuery],
    from_states=[StateEnum.DISABLED],
)
def return_loaned_item(bot: TelegramBot, update, state):
    """Receive callback for loan return.
    If not warehouse worker, ask warehouse workers for final approval
    """
    query = update.get_callback_query()
    userid = query.get_user().get_id()
    messageid = query.get_message().message_id
    callback_data = update.get_callback_query().get_data()

    try:
        assert callback_data == "item_return"
    except AssertionError:
        return

    loan = Loan.objects.get(
        notification_message=messageid,
        fkuser__profile__telegram_user__telegram_id=userid,
    )

    bot.answerCallbackQuery(
        update.get_callback_query().get_id(), text="Elaborazione in corso..."
    )

    approval = "warehouse.can_approve_return" in loan.fkuser.get_user_permissions()
    loan.return_date = timezone.now()
    loan.warehouse_staff_approved = approval
    loan.save()

    message = f"{loan.fkinventory_item.brand} {loan.fkinventory_item.model} restituito"

    if not approval:
        message += "\n\nIn attesa di approvazione dal magazziniere"

        warehouse_group = Group.objects.get(name="Magazziniere")

        for user in warehouse_group.user_set.all():
            if user.profile.telegram_user is None:
                continue

            msg_txt = (
                f"{loan.fkuser.first_name} {loan.fkuser.last_name} ha "
                f"riportato {loan.fkinventory_item.brand} {loan.fkinventory_item.model}. Confermi?",
            )

            bot.sendMessage(
                chat_id=user.profile.telegram_user.telegram_id,
                text=msg_txt,
                reply_markup=InlineKeyboardMarkup.a(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton.a(
                                text="✅ Sì",
                                callback_data=f"return_confirm-{loan.id}-{loan.notification_message}",
                            )
                        ]
                    ]
                ),
            )

    bot.editMessageText(
        message,
        chat_id=query.get_chat().get_id(),
        message_id=query.get_message().message_id,
    )


@processor(
    state_manager,
    update_types=[update_types.CallbackQuery],
    from_states=[StateEnum.DISABLED],
)
def confirm_return_item(bot: TelegramBot, update, state):
    """Receive return inline callback from warehouse worker
    Finalize loan return
    """
    query = update.get_callback_query()
    userid = query.get_user().get_id()
    messageid = query.get_message().message_id
    callback_data = update.get_callback_query().get_data()

    try:
        assert "return_confirm" in callback_data
    except AssertionError:
        return

    bot.answerCallbackQuery(
        update.get_callback_query().get_id(), text="Elaborazione in corso..."
    )

    _, loan_id, notification_message = callback_data.split("-")

    loan = Loan.objects.get(id=loan_id)

    # Check message id is the same we are expecting
    try:
        assert int(notification_message) == loan.notification_message
        django_user = User.objects.get(profile__telegram_user__telegram_id=userid)
        approval = "warehouse.can_approve_return" in django_user.get_user_permissions()
        assert approval
    except AssertionError:
        return

    loan.return_date = timezone.now()
    loan.warehouse_staff_approved = approval
    loan.save()

    # Tell warehouse worker we are good
    bot.editMessageText(
        query.get_message().get_text() + "\n\nConfermato",
        chat_id=query.get_chat().get_id(),
        message_id=messageid,
    )

    message = f"{loan.fkinventory_item.brand} {loan.fkinventory_item.model} restituito\n\nApprovazione ricevuta"
    # Update message for original loan user
    bot.editMessageText(
        message,
        chat_id=loan.fkuser.profile.telegram_user.telegram_id,
        message_id=loan.notification_message,
    )


@processor(
    state_manager,
    update_types=[update_types.PollAnswer],
    from_states=[StateEnum.DISABLED],
)
def manage_poll_answer_servizio(bot: TelegramBot, update, state):
    """Receive Poll answers for Servizio polls"""

    poll_id = update.poll_answer.poll_id
    user = update.poll_answer.get_user()
    answer = update.poll_answer.option_ids[0]

    try:
        servizio = Servizio.objects.get(poll_id=int(poll_id))
    except Servizio.DoesNotExist:
        return

    try:
        user_instance = User.objects.get(profile__telegram_user__telegram_id=user.id)
    except User.DoesNotExist:
        bot.sendMessage(
            settings.GROUP_CHAT_ID,
            text=f"@{user.username} non sei registrato al sito! La tua risposta non è stata formalizzata\n"
            "Apri una chat con questo bot e manda il comando /register",
        )
        return

    response_mapping = [
        ServizioResponse.ResponseEnum.ACCEPTED,
        ServizioResponse.ResponseEnum.MAYBE,
        ServizioResponse.ResponseEnum.REFUSED,
    ]

    answer_enum = response_mapping[answer]

    servizio_response = ServizioResponse(
        fkservizio=servizio, fkuser=user_instance, response=answer_enum
    )

    servizio_response.save()
