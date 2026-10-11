from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from servizio.models import Servizio, Timbratura
from volontario.models import Volontario

VALID_CF = "RSSMRA90A01H501W"
OTHER_CF = "VRDLGU85M01F205P"

User = get_user_model()


def local(dt) -> str:
    """Value for a datetime-local input."""
    return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")


class PresenzeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mario")
        self.mario = Volontario.objects.create(
            codice_fiscale=VALID_CF, nome="Mario", cognome="Rossi", user=self.user
        )
        self.luigi = Volontario.objects.create(
            codice_fiscale=OTHER_CF, nome="Luigi", cognome="Verdi"
        )
        self.start = (timezone.now() - timedelta(days=3)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        self.servizio = Servizio.objects.create(
            nome="Fiera",
            data_ora=self.start,
            data_ora_fine=self.start + timedelta(hours=4),
            send_message=False,
        )
        self.client.force_login(self.user)
        self.url_nuova = reverse("webapp:presenza_nuova")

    def post_nuova(self, clock_in, clock_out, servizio=None, notes=""):
        return self.client.post(
            self.url_nuova,
            {
                "fkservizio": servizio.pk if servizio else "",
                "clock_in": local(clock_in),
                "clock_out": local(clock_out) if clock_out else "",
                "notes": notes,
            },
        )

    # --- Aggiunta ---

    def test_add_presence_linked_to_servizio(self):
        response = self.post_nuova(
            self.start, self.start + timedelta(hours=3), self.servizio, "Dimenticato"
        )
        self.assertEqual(response.status_code, 302)
        entry = Timbratura.objects.get()
        self.assertEqual(entry.fkvolontario, self.mario)
        self.assertEqual(entry.fkservizio, self.servizio)
        self.assertEqual(entry.duration, 180)
        self.assertTrue(entry.inserita_manualmente)
        self.assertIsNone(entry.modificata_at)

        ore = self.client.get(response["Location"])
        self.assertContains(ore, "inserita a mano")

    def test_servizio_is_required(self):
        response = self.post_nuova(self.start, self.start + timedelta(hours=3))
        self.assertFormError(
            response.context["form"], "fkservizio", "Questo campo è obbligatorio."
        )
        self.assertFalse(Timbratura.objects.exists())

    def test_clock_out_is_required_for_new_entries(self):
        response = self.post_nuova(self.start, None, self.servizio)
        self.assertTrue(response.context["form"].errors["clock_out"])

    def test_form_lists_only_recent_started_servizi(self):
        Servizio.objects.create(
            nome="Futuro",
            data_ora=timezone.now() + timedelta(days=2),
            send_message=False,
        )
        Servizio.objects.create(
            nome="Vecchio",
            data_ora=timezone.now() - timedelta(days=90),
            send_message=False,
        )
        response = self.client.get(self.url_nuova)
        self.assertContains(response, "Fiera")
        self.assertNotContains(response, "Futuro")
        self.assertNotContains(response, "Vecchio")

    def test_rejects_invalid_times(self):
        cases = [
            # end before start
            (self.start + timedelta(hours=2), self.start, "dopo l&#x27;entrata"),
            # longer than 24h
            (self.start, self.start + timedelta(hours=25), "24 ore"),
            # far from the servizio
            (
                self.start - timedelta(days=1),
                self.start - timedelta(days=1, hours=-2),
                "non corrispondono al servizio",
            ),
        ]
        for clock_in, clock_out, error in cases:
            with self.subTest(error=error):
                response = self.post_nuova(clock_in, clock_out, self.servizio)
                self.assertContains(response, error)
        self.assertFalse(Timbratura.objects.exists())

    def test_rejects_future_times(self):
        servizio = Servizio.objects.create(
            nome="Oggi",
            data_ora=timezone.now() - timedelta(hours=1),
            send_message=False,
        )
        response = self.post_nuova(
            timezone.now() - timedelta(hours=1),
            timezone.now() + timedelta(hours=2),
            servizio,
        )
        self.assertContains(response, "nel futuro")

    def test_rejects_overlap(self):
        Timbratura.objects.create(
            fkvolontario=self.mario,
            clock_in=self.start + timedelta(hours=1),
            clock_out=self.start + timedelta(hours=2),
        )
        # Someone else's entry at the same time is not a conflict for Mario.
        Timbratura.objects.create(
            fkvolontario=self.luigi,
            clock_in=self.start + timedelta(hours=3),
            clock_out=self.start + timedelta(hours=4),
        )
        response = self.post_nuova(
            self.start, self.start + timedelta(hours=3), self.servizio
        )
        self.assertContains(response, "Si sovrappone")
        response = self.post_nuova(
            self.start + timedelta(hours=2),
            self.start + timedelta(hours=4),
            self.servizio,
        )
        self.assertEqual(response.status_code, 302)

    # --- Modifica ---

    def test_edit_own_entry(self):
        entry = Timbratura.objects.create(
            fkvolontario=self.mario,
            fkservizio=self.servizio,
            clock_in=self.start,
            clock_out=self.start + timedelta(hours=1),
        )
        url = reverse("webapp:presenza_modifica", args=[entry.pk])
        response = self.client.get(url)
        self.assertNotContains(response, 'name="fkservizio"')  # only times + notes

        response = self.client.post(
            url,
            {
                "clock_in": local(self.start),
                "clock_out": local(self.start + timedelta(hours=4)),
                "notes": "Uscita dimenticata",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.duration, 240)
        self.assertEqual(entry.fkservizio, self.servizio)  # unchanged
        self.assertIsNotNone(entry.modificata_at)
        self.assertFalse(entry.inserita_manualmente)
        self.assertContains(self.client.get(response["Location"]), "corretta")

    def test_close_open_entry(self):
        entry = Timbratura.objects.create(
            fkvolontario=self.mario,
            clock_in=timezone.now() - timedelta(hours=2),
        )
        url = reverse("webapp:presenza_modifica", args=[entry.pk])
        # Leaving the exit empty keeps the shift open.
        response = self.client.post(url, {"clock_in": local(entry.clock_in)})
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertIsNone(entry.clock_out)

        response = self.client.post(
            url,
            {
                "clock_in": local(entry.clock_in),
                "clock_out": local(timezone.now() - timedelta(minutes=10)),
            },
        )
        entry.refresh_from_db()
        self.assertIsNotNone(entry.clock_out)

    def test_cannot_edit_someone_elses_entry(self):
        entry = Timbratura.objects.create(
            fkvolontario=self.luigi,
            clock_in=self.start,
            clock_out=self.start + timedelta(hours=1),
        )
        url = reverse("webapp:presenza_modifica", args=[entry.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.post(url, {"clock_in": local(self.start)}).status_code, 404
        )

    def test_old_entries_are_read_only(self):
        old = timezone.now() - timedelta(days=90)
        entry = Timbratura.objects.create(
            fkvolontario=self.mario,
            clock_in=old,
            clock_out=old + timedelta(hours=1),
        )
        url = reverse("webapp:presenza_modifica", args=[entry.pk])
        response = self.client.get(url, follow=True)
        self.assertContains(response, "troppo vecchia")

        ore = self.client.get(
            reverse("webapp:profilo_sezione", args=["ore"]), {"anno": old.year}
        )
        self.assertNotContains(ore, url)
