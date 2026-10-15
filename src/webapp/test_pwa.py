import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from io import StringIO
from py_vapid import Vapid01
from py_vapid.utils import b64urlencode
from pywebpush import WebPushException

from servizio.models import Servizio, Timbratura
from servizio.timbrature import TimbraturaError, registra_entrata, registra_uscita
from volontario.models import Volontario

from . import push
from .models import PushSubscription

VALID_CF = "RSSMRA90A01H501W"

# Coppia di chiavi di test generata con `manage.py genvapid`.
VAPID = {
    "VAPID_PUBLIC_KEY": "BMOSQ-rM8QaKZzY-guJ4KA6k0BZRNi4u2pAOQdiUforIEN8VErjihb9Xvgx9hgnPKt0SX1m5Ng9bJB7gRRTRvec",
    "VAPID_PRIVATE_KEY": "eEJW0CByPNLi9r5I6drijx-_bleQrBkuHXYbwr2Uasc",
}

User = get_user_model()


class VolontarioTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mario")
        self.volontario = Volontario.objects.create(
            codice_fiscale=VALID_CF, nome="Mario", cognome="Rossi", user=self.user
        )

    def subscribe(self, endpoint="https://push.example/abc"):
        return PushSubscription.objects.create(
            volontario=self.volontario, endpoint=endpoint, p256dh="k", auth="a"
        )


class TimbratureTests(VolontarioTestCase):
    def test_entrata_links_servizio_in_corso(self):
        servizio = Servizio.objects.create(
            nome="Fiera",
            data_ora=timezone.now() - timedelta(hours=1),
            data_ora_fine=timezone.now() + timedelta(hours=1),
            send_message=False,
        )
        entry = registra_entrata(self.volontario)
        self.assertEqual(entry.fkservizio, servizio)

    def test_entrata_links_servizio_starting_within_an_hour(self):
        cases = [(timedelta(minutes=2), True), (timedelta(minutes=90), False)]
        for anticipo, collegata in cases:
            with self.subTest(anticipo=anticipo):
                servizio = Servizio.objects.create(
                    nome="Serata",
                    data_ora=timezone.now() + anticipo,
                    data_ora_fine=timezone.now() + anticipo + timedelta(hours=3),
                    send_message=False,
                )
                entry = registra_entrata(self.volontario)
                self.assertEqual(entry.fkservizio, servizio if collegata else None)
                Timbratura.objects.all().delete()
                servizio.delete()

    def test_double_entrata_and_missing_uscita(self):
        with self.assertRaises(TimbraturaError):
            registra_uscita(self.volontario)
        registra_entrata(self.volontario)
        with self.assertRaises(TimbraturaError):
            registra_entrata(self.volontario)
        self.assertIsNotNone(registra_uscita(self.volontario).clock_out)


@override_settings(**VAPID)
@patch("webapp.push.send_push_background")
class TurnoSignalTests(VolontarioTestCase):
    def test_clock_in_then_out(self, send):
        with self.captureOnCommitCallbacks(execute=True):
            entry = Timbratura.objects.create(fkvolontario=self.volontario)
        volontario_id, payload, _ttl = send.call_args.args
        self.assertEqual(volontario_id, VALID_CF)
        self.assertEqual(payload["tag"], push.TAG_TURNO)
        self.assertTrue(payload["requireInteraction"])
        self.assertEqual(payload["actions"][0]["action"], "uscita")

        entry.clock_out = timezone.now()
        with self.captureOnCommitCallbacks(execute=True):
            entry.save()
        self.assertEqual(send.call_args.args[1]["title"], "✅ Uscita registrata")

        # Editing an already closed entry notifies nobody.
        send.reset_mock()
        entry.notes = "corretta"
        with self.captureOnCommitCallbacks(execute=True):
            entry.save()
        send.assert_not_called()

    def test_entry_created_closed_is_silent(self, send):
        with self.captureOnCommitCallbacks(execute=True):
            Timbratura.objects.create(
                fkvolontario=self.volontario,
                clock_in=timezone.now() - timedelta(hours=2),
                clock_out=timezone.now(),
            )
        send.assert_not_called()

    @override_settings(VAPID_PRIVATE_KEY="")
    def test_disabled_without_keys(self, send):
        with self.captureOnCommitCallbacks(execute=True):
            Timbratura.objects.create(fkvolontario=self.volontario)
        send.assert_not_called()


@override_settings(**VAPID)
class SendPushTests(VolontarioTestCase):
    @patch("pywebpush.webpush")
    def test_sends_and_records_success(self, webpush):
        sub = self.subscribe()
        self.assertEqual(push.send_push(VALID_CF, {"title": "Ciao"}), 1)
        kwargs = webpush.call_args.kwargs
        self.assertEqual(kwargs["subscription_info"]["endpoint"], sub.endpoint)
        self.assertEqual(json.loads(kwargs["data"]), {"title": "Ciao"})
        sub.refresh_from_db()
        self.assertIsNotNone(sub.last_success_at)

    @patch("pywebpush.webpush")
    def test_gone_subscription_is_removed(self, webpush):
        self.subscribe()
        webpush.side_effect = WebPushException(
            "gone", response=MagicMock(status_code=410)
        )
        self.assertEqual(push.send_push(VALID_CF, {"title": "Ciao"}), 0)
        self.assertFalse(PushSubscription.objects.exists())

    def test_generated_keys_are_a_valid_pair(self):
        out = StringIO()
        call_command("genvapid", stdout=out, stderr=StringIO())
        keys = dict(line.split("=", 1) for line in out.getvalue().split())
        vapid = Vapid01.from_raw(keys["VAPID_PRIVATE_KEY"].encode())
        public = vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.assertEqual(b64urlencode(public), keys["VAPID_PUBLIC_KEY"])


@override_settings(**VAPID)
@patch("webapp.push.send_push_background")
class PushActionTests(VolontarioTestCase):
    url = reverse("webapp:push_action")

    def act(self, token):
        return self.client.post(
            self.url, json.dumps({"token": token}), content_type="application/json"
        ).json()

    def test_uscita_from_notification(self, _send):
        entry = Timbratura.objects.create(fkvolontario=self.volontario)
        token = push.notifica_in_servizio(entry)["actions"][0]["token"]

        result = self.act(token)
        self.assertEqual(result["title"], "✅ Uscita registrata")
        entry.refresh_from_db()
        self.assertIsNotNone(entry.clock_out)

        # Pressing the button again does not reopen or alter anything.
        self.assertEqual(self.act(token)["title"], "Nessun turno aperto")

    def test_entrata_from_reminder(self, _send):
        servizio = Servizio.objects.create(
            nome="Fiera",
            data_ora=timezone.now() + timedelta(minutes=30),
            send_message=False,
        )
        payload = push.notifica_promemoria_entrata(servizio, self.volontario)
        result = self.act(payload["actions"][0]["token"])
        self.assertEqual(result["tag"], push.TAG_TURNO)
        entry = Timbratura.objects.get(fkvolontario=self.volontario)
        self.assertEqual(entry.fkservizio, servizio)

    def test_forged_token(self, _send):
        self.assertEqual(self.act("not-a-token")["title"], "Azione scaduta")
        self.assertFalse(Timbratura.objects.exists())


class PwaViewTests(VolontarioTestCase):
    def test_manifest_and_service_worker(self):
        manifest = self.client.get(reverse("webapp:manifest"))
        self.assertEqual(manifest["Content-Type"], "application/manifest+json")
        self.assertEqual(manifest.json()["start_url"], "/app/")

        sw = self.client.get(reverse("webapp:service_worker"))
        self.assertEqual(sw["Content-Type"], "application/javascript")
        self.assertEqual(sw["Service-Worker-Allowed"], "/")
        self.assertContains(sw, reverse("webapp:push_action"))

    def test_subscribe_requires_login(self):
        response = self.client.post(
            reverse("webapp:push_subscribe"), "{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)

    def test_subscribe_and_unsubscribe(self):
        self.client.force_login(self.user)
        body = {
            "endpoint": "https://push.example/xyz",
            "keys": {"p256dh": "key", "auth": "secret"},
        }
        for _ in range(2):  # re-subscribing the same device updates it
            response = self.client.post(
                reverse("webapp:push_subscribe"),
                json.dumps(body),
                content_type="application/json",
            )
            self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(PushSubscription.objects.count(), 1)

        self.client.post(
            reverse("webapp:push_unsubscribe"),
            json.dumps({"endpoint": body["endpoint"]}),
            content_type="application/json",
        )
        self.assertFalse(PushSubscription.objects.exists())

    def test_subscribe_rejects_bad_payload(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("webapp:push_subscribe"),
            json.dumps({"endpoint": "http://insecure"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_timbra_from_home(self):
        self.client.force_login(self.user)
        url = reverse("webapp:timbra")

        response = self.client.post(url, {"azione": "entrata"}, follow=True)
        self.assertContains(response, "Entrata registrata")
        self.assertContains(response, "Timbra uscita")

        response = self.client.post(url, {"azione": "entrata"}, follow=True)
        self.assertContains(response, "già un&#x27;entrata aperta")

        response = self.client.post(url, {"azione": "uscita"}, follow=True)
        self.assertContains(response, "Uscita registrata")
        self.assertContains(response, "Timbra entrata")

    @override_settings(**VAPID)
    def test_home_shows_notification_setup_only_when_configured(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("webapp:home")), 'id="notifiche"')
        with self.settings(VAPID_PRIVATE_KEY=""):
            self.assertNotContains(
                self.client.get(reverse("webapp:home")), 'id="notifiche"'
            )
