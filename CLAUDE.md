# gesti-pc

Management tool for a group of "Protezione Civile" volunteers (Italian civil protection).

The system is administered via the **Django Admin** pages, but its primary interface for
laypeople is the **Telegram Bot** — its crown jewel. Every volunteer (Volontario) interacts
with the system through their linked Telegram account.

Two main functions:
- **Calendar / sign-up** — `Servizio` and `ScheduledTask` alert volunteers about upcoming
  events and tasks; sign-up happens through a Telegram poll.
- **Time-keeping** — volunteers clock in and out (`Timbratura`).

Volunteers are tracked by their Italian **Codice Fiscale** (tax code). All UI, data, and
messages are in **Italian** (locale `it-it`, timezone `Europe/Rome`).

## Tech stack

- **Python** ≥ 3.13 (`.python-version`)
- **Django** ≥ 6.0.1
- **python-telegram-bot[job-queue]** ≥ 22.5 — async bot framework; in-process `job_queue`
  handles all scheduling (no Celery)
- **python-codicefiscale** — Italian tax-code validation
- **gunicorn** — production WSGI server
- **Package manager: `uv`** (`uv.lock`). Use `uv run`, `uv add`, etc.
- **Linter/formatter: `ruff`**
- **Database: SQLite** (`src/db.sqlite3`)
- No Docker, no CI workflows yet.

## Layout

```
src/
├── manage.py
├── gesti_pc/          # Django project config (settings.py, urls.py, wsgi/asgi)
├── volontario/        # Volunteers, organizations, certifications, vehicles, objects
├── servizio/          # Services/events, scheduled tasks, checklists, time tracking
├── tg_bot/            # Telegram bot — primary user interface
│   ├── bot.py         # Core bot logic (~1800 lines): handlers + scheduled jobs
│   ├── models.py      # TelegramUser, LoginToken, AllertaMeteoStato
│   ├── oidc.py        # "Log in with Telegram" (OpenID Connect) client
│   ├── views.py       # Web login flow
│   └── management/commands/runbot.py
├── magazzino/         # Equipment/gear (dotazioni) management
├── webapp/            # Web app at /app/ — browser + Telegram Mini App (reports)
└── campo/             # Placeholder app (no models yet)
```

## Models by app

**volontario** (`src/volontario/models.py`)
- `Volontario` — volunteer; PK is `codice_fiscale`; linked to an org and a Django user
- `Organizzazione` — organization/group
- `Certificazione` / `CertificazioneVolontarioMap` — certifications and their M2M mapping
- `TipoOggetto` / `Oggetto` — generic objects owned by the org
- `TipoVeicolo` / `Veicolo` — vehicles (PK = targa/plate)

**servizio** (`src/servizio/models.py`)
- `Servizio` — an event volunteers sign up for; on save, sends a Telegram availability poll
- `ServizioType` — service category (equipment requirements + checklist templates)
- `VolontarioServizioMap` — M2M of volunteer ↔ service with poll response (Sì/No)
- `ChecklistTemplateItem` — template checklist items for a service type
- `ScheduledTask` — a task with a deadline and assigned volunteers
- `ChecklistItem` — checklist item for a `ScheduledTask` (tracks who/when completed)
- `Timbratura` — clock in/out entry; links to a `Servizio` or a `ScheduledTask`

**tg_bot** (`src/tg_bot/models.py`)
- `TelegramUser` — 1:1 link between Telegram ID and `Volontario`; tracks linking status
- `LoginToken` — one-time web-login token (10-min expiry)
- `AllertaMeteoStato` — last notified AllertaLOM alert level per (comune, category); used
  to de-duplicate weather-alert notifications

**webapp** (`src/webapp/models.py`)
- `PushSubscription` — a device's Web Push subscription, linked to a `Volontario`

**magazzino** (`src/magazzino/models.py`)
- `TipoDotazione` — equipment type
- `Dotazione` — equipment assigned to a volunteer (size, issue/return dates, active flag)
- `RequisitoServizioType` — equipment required per service type (drives reminders)

Side effects (e.g. sending/updating polls when a `Servizio` is created or changed) are
wired through Django **signals** — see `src/servizio/signals.py`.

## Telegram bot

Core logic lives in `src/tg_bot/bot.py`. `create_application()` registers all handlers.
Run with:

```bash
uv run src/manage.py runbot     # polling mode
```

**Commands:** `/start` (account linking via codice fiscale), `/help`, `/profilo`,
`/entrata` (clock in — auto-links to active Servizio), `/uscita` (clock out), `/ore`
(month-to-date hours), `/nuovoservizio` (multi-step create-Servizio conversation),
`/agenda` (next 14 days), `/login` (one-time web-login token), `/app` (opens the web app
as a Mini App; private chats only).

**Callback handlers:** poll answers → `VolontarioServizioMap`; clock-in/clock-out buttons; task-start and checklist-toggle (broadcasts updates to all
task volunteers).

**Scheduled jobs (job_queue):** service reminders (~30 min before, with clock-in button),
close expired polls, scheduled-task reminders (48h before), clock-out reminders (at end
time), equipment reminders (day before, 8 PM), weekly summary (Monday 9 AM Rome),
AllertaLOM weather-alert checks (per-category polling; see `src/tg_bot/allertalom.py`).

**AllertaLOM weather alerts** (`src/tg_bot/allertalom.py`): the `check_allerte` job polls the
Regione Lombardia AllertaLOM portal (XML endpoint) for the configured comune and posts a
message to the survey chat when an alert appears, escalates, improves, or clears (giallo/
arancione/rosso). Polling categories and their intervals are set via `ALLERTALOM_MONITOR`;
last-notified levels are stored in `AllertaMeteoStato` to avoid duplicate messages.

## Web access

`/` is a public homepage (logo + "Accedi con Telegram"). Web login (`src/tg_bot/views.py`):
- **Log in with Telegram (OpenID Connect)**: `/login/` → `oauth.telegram.org` (authorization
  code + PKCE) → `/auth/telegram/callback/`. `tg_bot/oidc.py` reads the discovery document,
  exchanges the code and verifies the `id_token` against Telegram's JWKS (iss, aud = bot ID,
  exp, nonce); the `id` claim (Telegram user ID) is matched to `TelegramUser`. Unlinked
  accounts are told to `/start` the bot. Needs `TELEGRAM_OIDC_CLIENT_SECRET` from @BotFather
  and the redirect URL `{SITE_URL}/auth/telegram/callback/` registered there.
- One-time token link from `/login` in the bot (`/auth/login/<token>/`).
- Inside the Telegram Mini App, `initData` login (see below).
All land on the web app (or the `?next=` page given to `/login/`).
Routes: `/`, `/admin/`, `/app/`, `/login/`, `/auth/telegram/callback/`, `/auth/login/<token>/`.

## Web app (`src/webapp/`)

Server-rendered Django templates, mobile-first, usable both in a browser and as a
**Telegram Mini App**. Pages: `/app/` (clock in/out, notification setup, personal hours), `/app/profilo/<sezione>/`
(the volunteer's own data, one page per section with a side menu that becomes a scrollable
tab bar on phones: `dati`, `dotazioni`, `formazione`, `servizi`, `ore`; see `profilo.py`, add a
section to `SEZIONI` + `_LOADERS` + a template in `templates/webapp/profilo/`), `/app/report/ore/` (hours report,
requires the `servizio.view_report_ore` permission; Chart.js charts + CSV export via `?formato=csv`).
- Auth: unauthenticated requests get `gate.html`. Inside Telegram it POSTs the signed
  `initData` to `/app/auth/telegram/` (validated in `telegram_auth.py`, HMAC with the bot
  token) and logs in the linked `Volontario.user`; in a browser it redirects to the homepage.
- Use the `webapp_view` decorator for new pages (login gate + iframe-embeddable for
  Telegram Web); add `permission_required(<perm>)` to restrict a page (shows the app's
  403 page). The hours report needs `servizio.view_report_ore` (custom permission on
  `Timbratura`, assigned to users or groups in the admin; superusers have it implicitly).
- Theme: CSS tokens in `static/webapp/app.css`; inside Telegram `app.js` adds `.tg` to
  `<html>` and the tokens follow the client's `--tg-theme-*` colors.
- Aggregations live in `reports.py` (hours computed in Python; a `Timbratura` counts in the
  month of its clock-in; open entries are excluded).
- **PWA**: installable (`/app/manifest.webmanifest`, service worker at `/app/sw.js` served
  with scope `/`). Web Push via `pywebpush` (`push.py`): `PushSubscription` stores each
  device; keys from `manage.py genvapid` → `VAPID_*` env vars (no keys = push disabled).
  A `Timbratura` post_save signal (`signals.py`) pushes the "in servizio" notification on
  clock-in (from any channel: app, bot, admin) and replaces it with a summary on clock-out.
  The bot's 30-min clock-in reminder and end-of-servizio clock-out reminder also go out
  as push. Notification buttons call `/app/push/azione/` with a signed token (no session).
  Push is unavailable inside Telegram's webview; on iOS only once added to the Home Screen.
- Clock-in/out logic shared with the app lives in `servizio/timbrature.py`.
- Mini Apps require HTTPS: the `/app` command and the chat menu button are enabled only
  when `SITE_URL` is `https://…`, which also switches session/CSRF cookies to
  `SameSite=None; Secure` and sets `CSRF_TRUSTED_ORIGINS`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token (required) |
| `TELEGRAM_SURVEY_CHAT_ID` | Group chat for polls/summaries (required) |
| `TELEGRAM_SURVEY_THREAD_ID` | Forum topic ID (optional) |
| `TELEGRAM_LOCKED_THREAD_IDS` | Comma-separated topic IDs kept closed |
| `TELEGRAM_NO_MESSAGE_THREAD_IDS` | Comma-separated topic IDs where only the bot may post |
| `TELEGRAM_OIDC_CLIENT_SECRET` | Client secret for "Log in with Telegram", from @BotFather (required for web login) |
| `TELEGRAM_OIDC_CLIENT_ID` | Optional; defaults to the bot's numeric ID (prefix of `TELEGRAM_BOT_TOKEN`) |
| `SITE_URL` | Base URL for login links and the Mini App (default `http://localhost:8000`); must be HTTPS for the Mini App |
| `ALLERTALOM_COMUNE_ISTAT` | ISTAT code of the comune to monitor (default `108055`) |
| `ALLERTALOM_MONITOR` | `cat:seconds` pairs, comma-separated (default `7:600,9:600,10:600,3:3600,8:3600`); empty disables the feature. Categories: 7=temporali, 9=idrogeologico, 10=idraulico, 8=vento forte, 2=neve, 3=incendi boschivi |
| `ALLERTALOM_HORIZON_HOURS` | Look-ahead window for an "active" alert (default `24`) |
| `ALLERTALOM_MIN_LEVEL` | Minimum level that triggers a notification (default `1`=giallo) |
| `ALLERTALOM_THREAD_ID` | Forum topic ID for weather alerts; empty (default) posts to the main "General" topic |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Web Push keys, from `manage.py genvapid`; empty disables push. Never rotate (existing devices stop receiving) |
| `VAPID_SUBJECT` | Contact for push services (`mailto:` or `https:`) |
| `DEBUG` | `"True"` to enable Django debug |
| `ALLOWED_HOSTS` | Comma-separated hosts (default `*`) |
| `STATIC_ROOT` / `MEDIA_ROOT` | File dirs |

See `.env.example`.

## Common commands

```bash
uv run src/manage.py migrate
uv run src/manage.py createsuperuser
uv run src/manage.py runbot          # start the Telegram bot
uv run src/manage.py runserver       # dev web server (admin)
uv run src/manage.py test            # Django tests
uv run ruff check src/ && uv run ruff format src/
```

## Tests

Standard Django `TestCase` per app (`src/<app>/tests.py`). Coverage is sparse and growing.
