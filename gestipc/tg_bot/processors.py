from django_tgbot.decorators import processor
from django.conf import settings
from django.contrib.auth.models import User, Group
from django_tgbot.state_manager import message_types, update_types, state_types
from django_tgbot.types.update import Update
from django_tgbot.types.inlinekeyboardmarkup import InlineKeyboardMarkup
from django_tgbot.types.inlinekeyboardbutton import InlineKeyboardButton
from django.utils import timezone

from .bot import state_manager
from .models import TelegramState, TelegramUser
from .bot import TelegramBot
from core.models import Profile
from warehouse.models import Loan
from hr.models import TelegramLink


@processor(state_manager, from_states=state_types.All)
def hello_world(bot: TelegramBot, update: Update, state: TelegramState):
    # bot.sendMessage(update.get_chat().get_id(), 'Hello!')
    pass


@processor(state_manager, from_states=state_types.All)
def register(bot: TelegramBot, update: Update, state: TelegramState):
    if getattr(update.get_message(), 'text', None) != "/register":
        return

    userid = update.get_user().get_id()
    tguser = TelegramUser.objects.get(telegram_id=userid)

    try:
        currentuser = tguser.profile.fkuser
    except (TelegramUser.profile.RelatedObjectDoesNotExist):
        new_verification_token = TelegramLink.objects.create(
            telegram_user=tguser)
        new_verification_token.save()
        bot.sendMessage(update.get_chat().get_id(
        ), f"Vai su {settings.OUTSIDE_URL}/hr/link_tg/{str(new_verification_token.security_code)} entro 10 minuti per collegare il tuo account")
    else:
        bot.sendMessage(update.get_chat().get_id(), "Sei già registrato")


def registration_complete(bot: TelegramBot, user):
    bot.sendMessage(user.profile.telegram_user.telegram_id,
                    f"Account {user.username} collegato correttamente")


def nuovo_servizio_callback(bot: TelegramBot):
    for user in User.objects.all():
        if user.profile.telegram_user is not None:
            bot.sendMessage(user.profile.telegram_user.telegram_id,
                            "Nuovo servizio creato, ci sei?")


def new_item_loaned_to_user(bot: TelegramBot, tg_user: TelegramUser, instance: Loan):
    msg = bot.sendMessage(
        tg_user.telegram_id,
        f"{instance.fkinventory_item.brand} {instance.fkinventory_item.model} assegnata a te\n\n"
        "Premi qui per riconsegnare",
        reply_markup=InlineKeyboardMarkup.a(inline_keyboard=[
            [InlineKeyboardButton.a(
                text="Riconsegna", callback_data="item_return")]
        ]))

    return msg


@processor(state_manager, from_states=state_types.All, update_types=[update_types.CallbackQuery])
def return_loaned_item(bot: TelegramBot, update, state):
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
        fkuser__profile__telegram_user__telegram_id=userid
    )

    bot.answerCallbackQuery(
        update.get_callback_query().get_id(),
        text='Elaborazione in corso...')

    approval = "can_approve_return" in loan.fkuser.get_user_permissions()
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

            bot.sendMessage(
                chat_id=user.profile.telegram_user.telegram_id,
                text=f"{loan.fkuser.first_name} {loan.fkuser.last_name} ha riportato {loan.fkinventory_item.brand} {loan.fkinventory_item.model}. Confermi?",
                reply_markup=InlineKeyboardMarkup.a(inline_keyboard=[
                    [InlineKeyboardButton.a(
                        text="✅ Sì", callback_data=f"return-confirm-{loan.id}-{loan.notification_message}")]
                ])
            )

    bot.editMessageText(
        message,
        chat_id=query.get_chat().get_id(),
        message_id=query.get_message().message_id)
