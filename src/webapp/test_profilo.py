from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from magazzino.models import Dotazione, TipoDotazione
from servizio.models import Servizio, Timbratura, VolontarioServizioMap
from tg_bot.models import TelegramUser
from volontario.models import (
    Certificazione,
    CertificazioneVolontarioMap,
    Organizzazione,
    Volontario,
)

VALID_CF = "RSSMRA90A01H501W"
OTHER_CF = "VRDLGU85M01F205P"

User = get_user_model()


def url(sezione):
    return reverse("webapp:profilo_sezione", args=[sezione])


class ProfiloTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mario")
        org = Organizzazione.objects.create(name="PC Roncello")
        self.mario = Volontario.objects.create(
            codice_fiscale=VALID_CF,
            nome="Mario",
            cognome="Rossi",
            fkorganizzazione=org,
            user=self.user,
        )
        self.luigi = Volontario.objects.create(
            codice_fiscale=OTHER_CF, nome="Luigi", cognome="Verdi"
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(url("dati"))
        self.assertTemplateUsed(response, "webapp/gate.html")

    def test_default_section_and_menu(self):
        response = self.client.get(reverse("webapp:profilo"))
        self.assertContains(response, "Dati personali")
        for sezione in ("dotazioni", "formazione", "servizi", "ore"):
            self.assertContains(response, url(sezione))
        self.assertContains(response, 'aria-current="page"', count=2)  # nav + menu

    def test_unknown_section(self):
        self.assertEqual(self.client.get(url("segreti")).status_code, 404)

    def test_user_without_volontario(self):
        self.client.force_login(User.objects.create_user(username="admin"))
        response = self.client.get(url("dotazioni"))
        self.assertContains(response, "non è associato a un volontario")

    def test_dati(self):
        TelegramUser.objects.create(
            telegram_id=42, volontario=self.mario, username="mariorossi"
        )
        response = self.client.get(url("dati"))
        self.assertContains(response, VALID_CF)
        self.assertContains(response, "1 Gennaio 1990")  # decoded from the CF
        self.assertContains(response, "PC Roncello")
        self.assertContains(response, "@mariorossi")

    def test_dotazioni(self):
        giacca = TipoDotazione.objects.create(nome="Giacca alta visibilità")
        stivali = TipoDotazione.objects.create(nome="Stivali")
        casco = TipoDotazione.objects.create(nome="Casco")
        Dotazione.objects.create(
            volontario=self.mario,
            tipo=giacca,
            taglia="L",
            data_assegnazione=date(2025, 3, 1),
        )
        Dotazione.objects.create(
            volontario=self.mario,
            tipo=stivali,
            data_assegnazione=date(2024, 1, 1),
            data_restituzione=date(2025, 1, 1),
        )
        Dotazione.objects.create(
            volontario=self.luigi, tipo=casco, data_assegnazione=date(2025, 1, 1)
        )

        response = self.client.get(url("dotazioni"))
        self.assertEqual(len(response.context["attive"]), 1)
        self.assertEqual(len(response.context["restituite"]), 1)
        self.assertContains(response, "Giacca alta visibilità")
        self.assertContains(response, "Taglia L")
        self.assertContains(response, "Stivali")
        self.assertNotContains(response, "Casco")  # someone else's

    def test_formazione(self):
        blsd = Certificazione.objects.create(nome="BLSD")
        haccp = Certificazione.objects.create(nome="HACCP")
        CertificazioneVolontarioMap.objects.create(
            fkvolontario=self.mario,
            fkcertificazione=blsd,
            data_conseguimento=date(2024, 5, 10),
        )
        CertificazioneVolontarioMap.objects.create(
            fkvolontario=self.luigi,
            fkcertificazione=haccp,
            data_conseguimento=date(2024, 5, 10),
        )
        response = self.client.get(url("formazione"))
        self.assertContains(response, "BLSD")
        self.assertContains(response, "10 Mag 2024")
        self.assertNotContains(response, "HACCP")

    def test_servizi(self):
        now = timezone.now()
        futuro = Servizio.objects.create(
            nome="Fiera di primavera",
            data_ora=now + timedelta(days=3),
            send_message=False,
        )
        passato = Servizio.objects.create(
            nome="Sagra", data_ora=now - timedelta(days=10), send_message=False
        )
        altrui = Servizio.objects.create(
            nome="Servizio di Luigi", data_ora=now, send_message=False
        )
        VolontarioServizioMap.objects.create(
            fkvolontario=self.mario, fkservizio=futuro, risposta="si"
        )
        VolontarioServizioMap.objects.create(
            fkvolontario=self.mario, fkservizio=passato, risposta="si"
        )
        VolontarioServizioMap.objects.create(
            fkvolontario=self.luigi, fkservizio=altrui, risposta="si"
        )
        Timbratura.objects.create(
            fkvolontario=self.mario,
            fkservizio=passato,
            clock_in=passato.data_ora,
            clock_out=passato.data_ora + timedelta(hours=3, minutes=30),
        )

        response = self.client.get(url("servizi"))
        self.assertEqual([r.fkservizio for r in response.context["prossimi"]], [futuro])
        self.assertEqual([r.fkservizio for r in response.context["passati"]], [passato])
        self.assertContains(response, "3h 30m")  # hours actually worked
        self.assertNotContains(response, "Servizio di Luigi")

    def test_ore_grouped_by_month_with_year_filter(self):
        def entry(vol, *start, hours):
            clock_in = timezone.make_aware(datetime(*start))
            Timbratura.objects.create(
                fkvolontario=vol,
                clock_in=clock_in,
                clock_out=clock_in + timedelta(hours=hours),
            )

        entry(self.mario, 2025, 3, 2, 9, hours=2)
        entry(self.mario, 2025, 3, 20, 9, hours=1)
        entry(self.mario, 2025, 5, 1, 9, hours=4)
        entry(self.mario, 2024, 7, 1, 9, hours=5)
        entry(self.luigi, 2025, 3, 2, 9, hours=8)

        response = self.client.get(url("ore"), {"anno": 2025})
        mesi = response.context["mesi"]
        self.assertEqual([m["data"].month for m in mesi], [5, 3])  # newest first
        self.assertEqual(mesi[1]["minuti"], 180)
        self.assertEqual(response.context["minuti_anno"], 420)
        self.assertIn(2024, response.context["anni"])
        self.assertContains(response, "Marzo 2025")

        # A year without entries falls back to the current one.
        response = self.client.get(url("ore"), {"anno": "1999"})
        self.assertEqual(response.context["anno"], timezone.localdate().year)
