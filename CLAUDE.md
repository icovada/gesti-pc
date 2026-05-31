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
│   ├── models.py      # TelegramUser, LoginToken, WebLoginRequest
│   ├── views.py       # Web login flow
│   └── management/commands/runbot.py
├── magazzino/         # Equipment/gear (dotazioni) management
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
- `WebLoginRequest` — web login pending Telegram approval (5-min expiry)

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
`/agenda` (next 14 days), `/login` (one-time web-login token).

**Callback handlers:** poll answers → `VolontarioServizioMap`; web-login approve/deny;
clock-in/clock-out buttons; task-start and checklist-toggle (broadcasts updates to all
task volunteers).

**Scheduled jobs (job_queue):** service reminders (~30 min before, with clock-in button),
close expired polls, scheduled-task reminders (48h before), clock-out reminders (at end
time), equipment reminders (day before, 8 PM), weekly summary (Monday 9 AM Rome).

## Web access

Web login is dual-path (`src/tg_bot/views.py`): a one-time token link from `/login` in the
bot, or a web form (`/login/`) that creates a `WebLoginRequest` approved from Telegram.
Routes: `/admin/`, `/auth/login/<token>/`, `/login/`, `/login/status/<token>/`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token (required) |
| `TELEGRAM_SURVEY_CHAT_ID` | Group chat for polls/summaries (required) |
| `TELEGRAM_SURVEY_THREAD_ID` | Forum topic ID (optional) |
| `TELEGRAM_LOCKED_THREAD_IDS` | Comma-separated topic IDs kept closed |
| `TELEGRAM_NO_MESSAGE_THREAD_IDS` | Comma-separated topic IDs where only the bot may post |
| `SITE_URL` | Base URL for login links (default `http://localhost:8000`) |
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
