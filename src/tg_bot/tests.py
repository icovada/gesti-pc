from unittest.mock import AsyncMock, MagicMock

from django.test import TestCase, override_settings
from telegram.constants import ChatMemberStatus

from tg_bot import bot
from tg_bot.models import TelegramUser
from volontario.models import Volontario

# A syntactically valid codice fiscale (Rossi Mario, 01/01/1990, Roma).
VALID_CF = "RSSMRA90A01H501W"


def _make_context(member_status=None, get_member_raises=False):
    """Build a fake ContextTypes object whose .bot is an AsyncMock."""
    context = MagicMock()
    context.bot = MagicMock()

    if get_member_raises:
        context.bot.get_chat_member = AsyncMock(side_effect=Exception("not found"))
    else:
        member = MagicMock()
        member.status = member_status
        context.bot.get_chat_member = AsyncMock(return_value=member)

    invite = MagicMock()
    invite.invite_link = "https://t.me/+abc123"
    context.bot.create_chat_invite_link = AsyncMock(return_value=invite)
    context.bot.send_message = AsyncMock()
    return context


@override_settings(TELEGRAM_SURVEY_CHAT_ID="-1001234567890")
class InviteToGroupTests(TestCase):
    """Tests for invite_to_group()."""

    async def test_no_chat_configured_skips(self):
        context = _make_context(member_status=ChatMemberStatus.LEFT)
        with override_settings(TELEGRAM_SURVEY_CHAT_ID=None):
            await bot.invite_to_group(context, 123)

        context.bot.get_chat_member.assert_not_called()
        context.bot.create_chat_invite_link.assert_not_called()
        context.bot.send_message.assert_not_called()

    async def test_existing_member_not_invited(self):
        context = _make_context(member_status=ChatMemberStatus.MEMBER)
        await bot.invite_to_group(context, 123)

        context.bot.create_chat_invite_link.assert_not_called()
        context.bot.send_message.assert_not_called()

    async def test_administrator_not_invited(self):
        context = _make_context(member_status=ChatMemberStatus.ADMINISTRATOR)
        await bot.invite_to_group(context, 123)

        context.bot.create_chat_invite_link.assert_not_called()
        context.bot.send_message.assert_not_called()

    async def test_banned_member_not_invited(self):
        context = _make_context(member_status=ChatMemberStatus.BANNED)
        await bot.invite_to_group(context, 123)

        context.bot.create_chat_invite_link.assert_not_called()
        context.bot.send_message.assert_not_called()

    async def test_left_member_gets_invite(self):
        context = _make_context(member_status=ChatMemberStatus.LEFT)
        await bot.invite_to_group(context, 123)

        context.bot.create_chat_invite_link.assert_called_once()
        context.bot.send_message.assert_called_once()
        kwargs = context.bot.send_message.call_args.kwargs
        self.assertEqual(kwargs["chat_id"], 123)
        self.assertIn("https://t.me/+abc123", kwargs["text"])

    async def test_unknown_member_gets_invite(self):
        # get_chat_member failing (e.g. user never seen by the chat) should
        # not block the invite.
        context = _make_context(get_member_raises=True)
        await bot.invite_to_group(context, 123)

        context.bot.create_chat_invite_link.assert_called_once()
        context.bot.send_message.assert_called_once()

    async def test_invite_link_failure_is_swallowed(self):
        context = _make_context(member_status=ChatMemberStatus.LEFT)
        context.bot.create_chat_invite_link = AsyncMock(
            side_effect=Exception("bot is not admin")
        )
        await bot.invite_to_group(context, 123)

        context.bot.send_message.assert_not_called()


@override_settings(TELEGRAM_SURVEY_CHAT_ID="-1001234567890")
class RegistrationInvitesToGroupTests(TestCase):
    """handle_codice_fiscale should invite the user once linking succeeds."""

    def setUp(self):
        self.volontario = Volontario.objects.create(
            codice_fiscale=VALID_CF, nome="Mario", cognome="Rossi"
        )
        self.tg_user = TelegramUser.objects.create(telegram_id=123)

    def _make_update(self, text):
        update = MagicMock()
        update.effective_user.id = 123
        update.message.text = text
        update.message.reply_text = AsyncMock()
        return update

    async def test_successful_linking_invites_to_group(self):
        update = self._make_update(VALID_CF)
        context = _make_context(member_status=ChatMemberStatus.LEFT)

        await bot.handle_codice_fiscale(update, context)

        # The account is linked...
        tg_user = await TelegramUser.objects.aget(telegram_id=123)
        self.assertEqual(str(tg_user.volontario_id), VALID_CF)
        # ...and an invite link was sent.
        context.bot.create_chat_invite_link.assert_called_once()
        context.bot.send_message.assert_called_once()

    async def test_invalid_cf_does_not_invite(self):
        update = self._make_update("TOO_SHORT")
        context = _make_context(member_status=ChatMemberStatus.LEFT)

        await bot.handle_codice_fiscale(update, context)

        context.bot.create_chat_invite_link.assert_not_called()
        context.bot.send_message.assert_not_called()
