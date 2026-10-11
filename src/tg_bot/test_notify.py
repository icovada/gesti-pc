from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from servizio.models import Servizio, Timbratura
from servizio.timbrature import registra_entrata
from tg_bot import notify
from tg_bot.models import TelegramUser
from volontario.models import Volontario

VALID_CF = "RSSMRA90A01H501W"


@override_settings(TELEGRAM_BOT_TOKEN="123:TOKEN")
class ClockInMessageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mario")
        self.volontario = Volontario.objects.create(
            codice_fiscale=VALID_CF, nome="Mario", cognome="Rossi", user=self.user
        )
        self.tg_user = TelegramUser.objects.create(
            telegram_id=42, volontario=self.volontario
        )

    @patch("servizio.timbrature.invia_messaggio_entrata_background")
    def test_app_clock_in_schedules_message(self, send):
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("webapp:timbra"), {"azione": "entrata"})
        entry = Timbratura.objects.get()
        send.assert_called_once_with(entry.pk)

    @patch("servizio.timbrature.invia_messaggio_entrata_background")
    def test_push_action_clock_in_schedules_message(self, send):
        from webapp import push

        servizio = Servizio.objects.create(
            nome="Fiera", data_ora=timezone.now(), send_message=False
        )
        token = push.notifica_promemoria_entrata(servizio, self.volontario)["actions"][
            0
        ]["token"]
        with self.captureOnCommitCallbacks(execute=True):
            push.esegui_azione(token)
        send.assert_called_once_with(Timbratura.objects.get().pk)

    @patch("tg_bot.notify._send", new_callable=AsyncMock)
    def test_message_has_clock_out_button(self, send):
        servizio = Servizio.objects.create(
            nome="Fiera <di> primavera", data_ora=timezone.now(), send_message=False
        )
        with patch("servizio.timbrature.invia_messaggio_entrata_background"):
            entry = registra_entrata(self.volontario, servizio)

        notify.invia_messaggio_entrata(entry.pk)
        chat_id, text = send.await_args.args
        self.assertEqual(chat_id, 42)
        self.assertIn("<b>Fiera &lt;di&gt; primavera</b>", text)
        button = notify.CLOCK_OUT_KEYBOARD.inline_keyboard[0][0]
        self.assertEqual(button.callback_data, "clock_out")  # handled by the bot

    @patch("tg_bot.notify._send", new_callable=AsyncMock)
    def test_no_message_without_telegram_or_when_closed(self, send):
        entry = Timbratura.objects.create(
            fkvolontario=self.volontario,
            clock_in=timezone.now() - timedelta(hours=1),
            clock_out=timezone.now(),
        )
        notify.invia_messaggio_entrata(entry.pk)  # already clocked out
        self.tg_user.delete()
        open_entry = Timbratura.objects.create(fkvolontario=self.volontario)
        notify.invia_messaggio_entrata(open_entry.pk)  # no Telegram account
        send.assert_not_awaited()
