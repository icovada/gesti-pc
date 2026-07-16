from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from telegram.constants import ChatMemberStatus

from tg_bot import allertalom, bot
from tg_bot.models import AllertaMeteoStato, TelegramUser
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


# Sample AllertaLOM XML response (trimmed to a few hourly items).
SAMPLE_XML = """<List>
<item><nomeZonaOmogenea>Nodo Idraulico di Milano</nomeZonaOmogenea><codiceZonaOmogenea>IM-09</codiceZonaOmogenea><dtPrevisione>1784210400000</dtPrevisione><cdLivello>0</cdLivello><livello>Codice VERDE</livello></item>
<item><nomeZonaOmogenea>Nodo Idraulico di Milano</nomeZonaOmogenea><codiceZonaOmogenea>IM-09</codiceZonaOmogenea><dtPrevisione>1784214000000</dtPrevisione><cdLivello>1</cdLivello><livello>Codice GIALLO</livello></item>
<item><nomeZonaOmogenea>Nodo Idraulico di Milano</nomeZonaOmogenea><codiceZonaOmogenea>IM-09</codiceZonaOmogenea><dtPrevisione>1784217600000</dtPrevisione><cdLivello>-1</cdLivello><livello>Nessuna Previsione</livello></item>
</List>"""


def _item(level, dt, livello="", zona="Nodo Idraulico di Milano", codice="IM-09"):
    """Build a single forecast item dict as produced by parse_forecast()."""
    return {
        "dt": dt,
        "cd_livello": level,
        "livello": livello or f"Codice {level}",
        "nome_zona": zona,
        "codice_zona": codice,
    }


def _alert(level, livello="", start=None, end=None, segments=None):
    """Build an alert dict as produced by current_alert().

    If segments is not given but start/end are, a single segment is synthesised.
    """
    if segments is None:
        segments = []
        if start and end:
            segments = [
                {
                    "cd_livello": level,
                    "livello": livello or f"Codice {level}",
                    "start": start,
                    "end": end,
                }
            ]
    return {
        "cd_livello": level,
        "livello": livello or f"Codice {level}",
        "nome_zona": "Nodo Idraulico di Milano",
        "codice_zona": "IM-09",
        "start": start,
        "end": end,
        "segments": segments,
    }


class ParseForecastTests(TestCase):
    """Tests for allertalom.parse_forecast()."""

    def test_parses_all_items(self):
        items = allertalom.parse_forecast(SAMPLE_XML)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["cd_livello"], 0)
        self.assertEqual(items[1]["livello"], "Codice GIALLO")
        self.assertEqual(items[2]["cd_livello"], -1)
        self.assertEqual(items[0]["nome_zona"], "Nodo Idraulico di Milano")
        self.assertEqual(items[0]["codice_zona"], "IM-09")

    def test_dt_is_timezone_aware(self):
        items = allertalom.parse_forecast(SAMPLE_XML)
        self.assertIsNotNone(items[0]["dt"].tzinfo)
        # Items are hourly: consecutive dt differ by one hour.
        self.assertEqual(items[1]["dt"] - items[0]["dt"], timedelta(hours=1))

    def test_ignores_unparsable_items(self):
        xml = "<List><item><cdLivello>1</cdLivello></item></List>"  # no dtPrevisione
        self.assertEqual(allertalom.parse_forecast(xml), [])


class CurrentAlertTests(TestCase):
    """Tests for allertalom.current_alert()."""

    def test_returns_max_level_in_window(self):
        now = timezone.now()
        items = [
            _item(0, now + timedelta(hours=1)),
            _item(2, now + timedelta(hours=3)),
            _item(1, now + timedelta(hours=5)),
        ]
        alert = allertalom.current_alert(items, now, 24)
        self.assertEqual(alert["cd_livello"], 2)

    def test_none_when_all_outside_horizon(self):
        now = timezone.now()
        items = [_item(3, now + timedelta(hours=48))]
        self.assertIsNone(allertalom.current_alert(items, now, 24))

    def test_ignores_no_forecast_items(self):
        now = timezone.now()
        items = [_item(-1, now + timedelta(hours=2))]
        self.assertIsNone(allertalom.current_alert(items, now, 24))

    def test_none_when_empty(self):
        self.assertIsNone(allertalom.current_alert([], timezone.now(), 24))

    def test_includes_current_hour_bucket(self):
        now = timezone.now()
        # Bucket started 30 min ago (dt < now) but is still the current hour.
        items = [_item(1, now - timedelta(minutes=30))]
        alert = allertalom.current_alert(items, now, 24)
        self.assertEqual(alert["cd_livello"], 1)

    def test_reports_alert_start_and_end(self):
        now = timezone.now()
        # Alert issued in advance: verde now, giallo from +5h to +7h, verde after.
        items = [
            _item(0, now),
            _item(1, now + timedelta(hours=5)),
            _item(2, now + timedelta(hours=6)),
            _item(1, now + timedelta(hours=7)),
            _item(0, now + timedelta(hours=8)),
        ]
        alert = allertalom.current_alert(items, now, 24, min_level=1)
        self.assertEqual(alert["cd_livello"], 2)
        self.assertEqual(alert["start"], now + timedelta(hours=5))
        # end = last elevated bucket (+7h) plus one hour.
        self.assertEqual(alert["end"], now + timedelta(hours=8))

    def test_no_period_when_below_min_level(self):
        now = timezone.now()
        items = [_item(1, now + timedelta(hours=2))]
        alert = allertalom.current_alert(items, now, 24, min_level=2)
        self.assertIsNone(alert["start"])
        self.assertIsNone(alert["end"])
        self.assertEqual(alert["segments"], [])

    def test_segments_split_by_severity(self):
        now = timezone.now()
        # Two giallo hours, then arancione, then giallo again.
        items = [
            _item(1, now + timedelta(hours=1)),
            _item(1, now + timedelta(hours=2)),
            _item(2, now + timedelta(hours=3)),
            _item(1, now + timedelta(hours=4)),
        ]
        segs = allertalom.current_alert(items, now, 24, min_level=1)["segments"]
        self.assertEqual([s["cd_livello"] for s in segs], [1, 2, 1])
        # The two consecutive giallo hours are merged into one segment.
        self.assertEqual(segs[0]["start"], now + timedelta(hours=1))
        self.assertEqual(segs[0]["end"], now + timedelta(hours=3))
        self.assertEqual(segs[1]["cd_livello"], 2)

    def test_gap_splits_same_level_segments(self):
        now = timezone.now()
        # Giallo, verde (gap), giallo → two separate giallo segments.
        items = [
            _item(1, now + timedelta(hours=1)),
            _item(0, now + timedelta(hours=2)),
            _item(1, now + timedelta(hours=3)),
        ]
        segs = allertalom.current_alert(items, now, 24, min_level=1)["segments"]
        self.assertEqual(len(segs), 2)


class BuildMessageTests(TestCase):
    """Tests for allertalom.build_message() wording per transition."""

    def test_new_alert(self):
        alert = _item(1, timezone.now(), "Codice GIALLO")
        msg = allertalom.build_message(7, alert, 0, 1, "108055")
        self.assertIn("Nuova allerta", msg)
        self.assertIn("Temporali", msg)
        self.assertIn("GIALLO", msg)

    def test_escalation(self):
        alert = _item(2, timezone.now(), "Codice ARANCIONE")
        msg = allertalom.build_message(7, alert, 1, 2, "108055")
        self.assertIn("peggioramento", msg)
        self.assertIn("ARANCIONE", msg)

    def test_improvement(self):
        alert = _item(1, timezone.now(), "Codice GIALLO")
        msg = allertalom.build_message(7, alert, 2, 1, "108055")
        self.assertIn("miglioramento", msg)

    def test_rientro(self):
        alert = _item(0, timezone.now(), "Codice VERDE")
        msg = allertalom.build_message(9, alert, 1, 0, "108055")
        self.assertIn("Rientro", msg)
        self.assertIn("VERDE", msg)
        self.assertIn("Rischio idrogeologico", msg)

    def test_shows_start_and_end_when_available(self):
        start = timezone.make_aware(datetime(2026, 7, 16, 15, 0))
        end = timezone.make_aware(datetime(2026, 7, 16, 21, 0))
        alert = _alert(1, "Codice GIALLO", start=start, end=end)
        msg = allertalom.build_message(7, alert, 0, 1, "108055")
        self.assertIn("16/07 ore 15:00", msg)
        self.assertIn("16/07 ore 21:00", msg)

    def test_falls_back_when_no_period(self):
        alert = _alert(1, "Codice GIALLO")  # start/end None
        msg = allertalom.build_message(7, alert, 0, 1, "108055")
        self.assertIn("prossime 24 ore", msg)

    def test_shows_severity_timeline_with_multiple_segments(self):
        base = timezone.make_aware(datetime(2026, 7, 16, 15, 0))
        segments = [
            {
                "cd_livello": 1,
                "livello": "Codice GIALLO",
                "start": base,
                "end": base + timedelta(hours=2),
            },
            {
                "cd_livello": 2,
                "livello": "Codice ARANCIONE",
                "start": base + timedelta(hours=2),
                "end": base + timedelta(hours=5),
            },
            {
                "cd_livello": 1,
                "livello": "Codice GIALLO",
                "start": base + timedelta(hours=5),
                "end": base + timedelta(hours=6),
            },
        ]
        alert = _alert(2, "Codice ARANCIONE", segments=segments)
        msg = allertalom.build_message(7, alert, 0, 2, "108055")
        self.assertIn("Evoluzione prevista", msg)
        self.assertIn("Livello massimo", msg)
        self.assertIn("Arancione", msg)
        self.assertIn("Giallo", msg)
        self.assertIn("16/07 15:00", msg)  # first giallo segment start
        self.assertIn("16/07 20:00", msg)  # arancione segment end (15:00 + 5h)


def _job_context(categories):
    """Fake context for check_allerte with a job carrying the category list."""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    context.job = MagicMock()
    context.job.data = {"categories": categories}
    return context


@override_settings(
    TELEGRAM_SURVEY_CHAT_ID="-1001234567890",
    ALLERTALOM_THREAD_ID=None,
    ALLERTALOM_COMUNE_ISTAT="108055",
    ALLERTALOM_MIN_LEVEL=1,
    ALLERTALOM_HORIZON_HOURS=24,
)
class CheckAllerteTests(TestCase):
    """Tests for the check_allerte scheduled job."""

    async def _run(self, items):
        context = _job_context([7])
        with patch.object(allertalom, "fetch_forecast", AsyncMock(return_value=items)):
            await bot.check_allerte(context)
        return context

    async def test_new_alert_notifies_and_stores_state(self):
        now = timezone.now()
        context = await self._run([_item(1, now, "Codice GIALLO")])

        context.bot.send_message.assert_called_once()
        # Alerts go to the main topic ("General") → message_thread_id omitted (None).
        self.assertIsNone(
            context.bot.send_message.call_args.kwargs["message_thread_id"]
        )
        state = await AllertaMeteoStato.objects.aget(
            cd_istat_comune="108055", cd_tipologia_gis=7
        )
        self.assertEqual(state.cd_livello, 1)
        self.assertEqual(state.nome_zona, "Nodo Idraulico di Milano")

    async def test_verde_first_run_does_not_notify(self):
        now = timezone.now()
        context = await self._run([_item(0, now, "Codice VERDE")])

        context.bot.send_message.assert_not_called()
        state = await AllertaMeteoStato.objects.aget(
            cd_istat_comune="108055", cd_tipologia_gis=7
        )
        self.assertEqual(state.cd_livello, 0)

    async def test_unchanged_level_does_not_renotify(self):
        now = timezone.now()
        items = [_item(1, now, "Codice GIALLO")]
        context = _job_context([7])
        with patch.object(allertalom, "fetch_forecast", AsyncMock(return_value=items)):
            await bot.check_allerte(context)
            context.bot.send_message.reset_mock()
            await bot.check_allerte(context)
        context.bot.send_message.assert_not_called()

    async def test_escalation_notifies(self):
        now = timezone.now()
        await self._run([_item(1, now, "Codice GIALLO")])
        context = await self._run([_item(2, now, "Codice ARANCIONE")])

        context.bot.send_message.assert_called_once()
        self.assertIn(
            "peggioramento", context.bot.send_message.call_args.kwargs["text"]
        )
        state = await AllertaMeteoStato.objects.aget(
            cd_istat_comune="108055", cd_tipologia_gis=7
        )
        self.assertEqual(state.cd_livello, 2)

    async def test_rientro_notifies(self):
        now = timezone.now()
        await self._run([_item(1, now, "Codice GIALLO")])
        context = await self._run([_item(0, now, "Codice VERDE")])

        context.bot.send_message.assert_called_once()
        self.assertIn("Rientro", context.bot.send_message.call_args.kwargs["text"])
        state = await AllertaMeteoStato.objects.aget(
            cd_istat_comune="108055", cd_tipologia_gis=7
        )
        self.assertEqual(state.cd_livello, 0)

    async def test_fetch_error_does_not_notify_or_store(self):
        context = _job_context([7])
        with patch.object(
            allertalom, "fetch_forecast", AsyncMock(side_effect=Exception("boom"))
        ):
            await bot.check_allerte(context)

        context.bot.send_message.assert_not_called()
        self.assertEqual(await AllertaMeteoStato.objects.acount(), 0)

    async def test_no_chat_configured_skips_fetch(self):
        context = _job_context([7])
        with override_settings(TELEGRAM_SURVEY_CHAT_ID=None):
            with patch.object(allertalom, "fetch_forecast", AsyncMock()) as mock_fetch:
                await bot.check_allerte(context)
            mock_fetch.assert_not_called()
        context.bot.send_message.assert_not_called()
