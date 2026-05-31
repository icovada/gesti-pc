from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .models import Servizio


class ServizioPollSignalTests(TestCase):
    """Tests for the poll-management signals on the Servizio model."""

    def setUp(self):
        self.data_ora = timezone.now() + timedelta(days=1)

    @patch("servizio.signals.send_availability_poll")
    def test_create_with_send_message_sends_poll(self, mock_send):
        with self.captureOnCommitCallbacks(execute=True):
            servizio = Servizio.objects.create(
                nome="Servizio A", data_ora=self.data_ora, send_message=True
            )

        mock_send.assert_called_once_with(servizio)

    @patch("servizio.signals.send_availability_poll")
    def test_create_without_send_message_does_not_send(self, mock_send):
        with self.captureOnCommitCallbacks(execute=True):
            Servizio.objects.create(
                nome="Servizio A", data_ora=self.data_ora, send_message=False
            )

        mock_send.assert_not_called()

    @patch("servizio.signals.send_availability_poll")
    def test_create_with_existing_poll_id_does_not_send(self, mock_send):
        with self.captureOnCommitCallbacks(execute=True):
            Servizio.objects.create(
                nome="Servizio A",
                data_ora=self.data_ora,
                send_message=True,
                poll_id="poll-1",
            )

        mock_send.assert_not_called()

    @patch("servizio.signals.send_availability_poll")
    def test_enabling_send_message_sends_poll(self, mock_send):
        servizio = Servizio.objects.create(
            nome="Servizio A", data_ora=self.data_ora, send_message=False
        )
        mock_send.reset_mock()

        servizio.send_message = True
        with self.captureOnCommitCallbacks(execute=True):
            servizio.save()

        mock_send.assert_called_once_with(servizio)

    @patch("servizio.signals.notify_poll_update")
    def test_content_change_posts_poll_update(self, mock_notify):
        servizio = Servizio.objects.create(
            nome="Servizio A",
            data_ora=self.data_ora,
            send_message=True,
            poll_id="poll-1",
            poll_message_id=123,
        )

        servizio.nome = "Servizio B"
        with self.captureOnCommitCallbacks(execute=True):
            servizio.save()

        mock_notify.assert_called_once_with(servizio, 123)

    @patch("servizio.signals.notify_poll_update")
    def test_data_ora_change_posts_poll_update(self, mock_notify):
        servizio = Servizio.objects.create(
            nome="Servizio A",
            data_ora=self.data_ora,
            send_message=True,
            poll_id="poll-1",
            poll_message_id=123,
        )

        servizio.data_ora = self.data_ora + timedelta(hours=2)
        with self.captureOnCommitCallbacks(execute=True):
            servizio.save()

        mock_notify.assert_called_once_with(servizio, 123)

    @patch("servizio.signals.notify_poll_update")
    def test_content_change_on_closed_poll_does_not_update(self, mock_notify):
        servizio = Servizio.objects.create(
            nome="Servizio A",
            data_ora=self.data_ora,
            send_message=True,
            poll_id="poll-1",
            poll_message_id=123,
            poll_closed=True,
        )

        servizio.nome = "Servizio B"
        with self.captureOnCommitCallbacks(execute=True):
            servizio.save()

        mock_notify.assert_not_called()

    @patch("servizio.signals.notify_poll_update")
    def test_content_change_without_poll_does_not_update(self, mock_notify):
        servizio = Servizio.objects.create(
            nome="Servizio A", data_ora=self.data_ora, send_message=False
        )

        servizio.nome = "Servizio B"
        with self.captureOnCommitCallbacks(execute=True):
            servizio.save()

        mock_notify.assert_not_called()

    @patch("servizio.signals.notify_poll_update")
    @patch("servizio.signals.send_availability_poll")
    def test_unrelated_change_does_not_trigger_poll(self, mock_send, mock_notify):
        servizio = Servizio.objects.create(
            nome="Servizio A",
            data_ora=self.data_ora,
            send_message=True,
            poll_id="poll-1",
            poll_message_id=123,
        )
        mock_send.reset_mock()

        servizio.notification_sent = True
        with self.captureOnCommitCallbacks(execute=True):
            servizio.save()

        mock_send.assert_not_called()
        mock_notify.assert_not_called()
