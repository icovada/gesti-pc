from django_tgbot.decorators import processor
from django.conf import settings
from django.contrib.auth.models import User
from django_tgbot.state_manager import message_types, update_types, state_types
from django_tgbot.types.update import Update
from .bot import state_manager
from .models import TelegramState
from .bot import TelegramBot
from core.models import Profile
from hr.models import TelegramLink


@processor(state_manager, from_states=state_types.All)
def hello_world(bot: TelegramBot, update: Update, state: TelegramState):
    # bot.sendMessage(update.get_chat().get_id(), 'Hello!')
    pass


@processor(state_manager, from_states=state_types.All)
def register(bot: TelegramBot, update: Update, state: TelegramState):
    if update.get_message().text != "/register":
        return

    userid = update.get_user().get_id()

    try:
        currentuser = Profile.objects.get(telegram_user_id=userid)
    except Profile.DoesNotExist:
        new_verification_token = TelegramLink.objects.create(
            telegram_user_id=userid)
        new_verification_token.save()
        bot.sendMessage(update.get_chat().get_id(
        ), f"Vai su {settings.OUTSIDE_URL}/hr/link_tg/{str(new_verification_token.security_code)} entro 10 minuti per collegare il tuo account")
    else:
        bot.sendMessage(update.get_chat().get_id(), "Sei già registrato")


def registration_complete(bot: TelegramBot, user):
    bot.sendMessage(user.profile.telegram_user_id,
                    f"Account {user.username} collegato correttamente")


def nuovo_servizio_callback(bot: TelegramBot):
    for user in User.objects.all():
        if user.profile.telegram_user_id is not None:
            bot.sendMessage(user.profile.telegram_user_id, "Nuovo servizio creato, ci sei?")