"""Notifiche Web Push (PWA): invio, contenuti e azioni dai pulsanti delle notifiche.

Le notifiche hanno un `tag`: una nuova notifica con lo stesso tag sostituisce la
precedente sul dispositivo. "turno" è la notifica "in servizio", che viene
aggiornata a fine servizio e sostituita dal riepilogo all'uscita.
"""

import json
import logging
import threading
from datetime import timedelta
from functools import lru_cache

from django.conf import settings
from django.core import signing
from django.db import close_old_connections
from django.utils import timezone

from servizio.models import Servizio, Timbratura
from servizio.timbrature import TimbraturaError, registra_entrata
from volontario.models import Volontario

from .models import PushSubscription
from .templatetags.humanize_ore import minuti_ore

logger = logging.getLogger(__name__)

TAG_TURNO = "turno"
TAG_ENTRATA = "entrata"
ACTION_SALT = "webapp.push-action"
ACTION_MAX_AGE = timedelta(days=2)


def is_configured() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


@lru_cache(maxsize=1)
def _vapid(private_key: str):
    from py_vapid import Vapid01

    return Vapid01.from_raw(private_key.encode())


def send_push(volontario_id: str, payload: dict, ttl: int = 3600) -> int:
    """Invia la notifica a tutti i dispositivi del volontario; restituisce quanti l'hanno ricevuta."""
    if not is_configured():
        return 0

    from pywebpush import WebPushException, webpush

    data = json.dumps(payload)
    sent = 0
    for sub in PushSubscription.objects.filter(volontario_id=volontario_id):
        try:
            webpush(
                subscription_info=sub.as_subscription_info(),
                data=data,
                vapid_private_key=_vapid(settings.VAPID_PRIVATE_KEY),
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                ttl=ttl,
                timeout=10,
                headers={"Urgency": payload.get("urgency", "normal")},
            )
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                # Iscrizione revocata o scaduta: il dispositivo non la userà più.
                logger.info("Removing expired push subscription %s", sub.pk)
                sub.delete()
            else:
                logger.warning("Push to subscription %s failed: %s", sub.pk, e)
            continue
        except Exception:
            logger.exception("Push to subscription %s failed", sub.pk)
            continue
        sub.last_success_at = timezone.now()
        sub.save(update_fields=["last_success_at"])
        sent += 1
    return sent


def send_push_background(volontario_id: str, payload: dict, ttl: int = 3600) -> None:
    """Come send_push, ma senza bloccare il chiamante (bot o richiesta web)."""
    if not is_configured():
        return

    def run():
        try:
            send_push(volontario_id, payload, ttl)
        finally:
            close_old_connections()

    threading.Thread(target=run, daemon=True).start()


# --- Azioni dai pulsanti delle notifiche -------------------------------------


def _action_token(**data) -> str:
    return signing.dumps(data, salt=ACTION_SALT, compress=True)


def esegui_azione(token: str) -> dict:
    """Esegue l'azione firmata di un pulsante; restituisce la notifica di conferma."""
    try:
        data = signing.loads(
            token, salt=ACTION_SALT, max_age=ACTION_MAX_AGE.total_seconds()
        )
    except signing.BadSignature:
        return _notifica("Azione scaduta", "Apri l'app per timbrare.", tag=TAG_TURNO)

    if data.get("a") == "uscita":
        entry = (
            Timbratura.objects.filter(pk=data.get("t"))
            .select_related("fkvolontario")
            .first()
        )
        if entry is None or entry.clock_out is not None:
            return _notifica(
                "Nessun turno aperto", "L'uscita era già stata registrata."
            )
        entry.clock_out = timezone.now()
        entry.save(update_fields=["clock_out"])
        # Il segnale invia anche la notifica di riepilogo agli altri dispositivi.
        return notifica_uscita(entry)

    if data.get("a") == "entrata":
        volontario = Volontario.objects.filter(pk=data.get("v")).first()
        servizio = Servizio.objects.filter(pk=data.get("s")).first()
        if volontario is None:
            return _notifica("Errore", "Volontario non trovato.")
        try:
            entry = registra_entrata(volontario, servizio)
        except TimbraturaError as e:
            return _notifica("Entrata non registrata", str(e), tag=TAG_ENTRATA)
        return notifica_in_servizio(entry)

    return _notifica("Azione non valida", "Apri l'app per timbrare.")


# --- Contenuti delle notifiche ------------------------------------------------


def _notifica(title: str, body: str, **options) -> dict:
    return {"title": title, "body": body, "url": "/app/", **options}


def _azione(action: str, title: str, token: str) -> dict:
    return {"action": action, "title": title, "token": token}


def _ora(dt) -> str:
    return f"{timezone.localtime(dt):%H:%M}"


def _durata(entry: Timbratura) -> str:
    return minuti_ore(entry.duration)


def notifica_in_servizio(entry: Timbratura) -> dict:
    """Notifica "in servizio", resta visibile finché non si timbra l'uscita."""
    dove = f" · {entry.fkservizio.nome}" if entry.fkservizio_id else ""
    return _notifica(
        "🟢 Sei in servizio",
        f"Dalle {_ora(entry.clock_in)}{dove}. Ricordati di timbrare l'uscita.",
        tag=TAG_TURNO,
        silent=True,
        requireInteraction=True,
        close_tags=[TAG_ENTRATA],
        actions=[
            _azione(
                "uscita", "Timbra uscita", _action_token(a="uscita", t=str(entry.pk))
            )
        ],
    )


def notifica_fine_servizio(entry: Timbratura, servizio: Servizio) -> dict:
    """Aggiorna la notifica "in servizio" quando il servizio è terminato."""
    return _notifica(
        "⏰ Servizio terminato",
        f"«{servizio.nome}» è finito alle {_ora(servizio.data_ora_fine)}. "
        "Ricordati di timbrare l'uscita!",
        tag=TAG_TURNO,
        renotify=True,
        requireInteraction=True,
        urgency="high",
        actions=[
            _azione(
                "uscita", "Timbra uscita", _action_token(a="uscita", t=str(entry.pk))
            )
        ],
    )


def notifica_uscita(entry: Timbratura) -> dict:
    return _notifica(
        "✅ Uscita registrata",
        f"Alle {_ora(entry.clock_out)} · durata {_durata(entry)}. Grazie!",
        tag=TAG_TURNO,
        silent=True,
    )


def notifica_promemoria_entrata(servizio: Servizio, volontario: Volontario) -> dict:
    return _notifica(
        f"⏰ Tra 30 minuti: {servizio.nome}",
        f"Inizio alle {_ora(servizio.data_ora)}. Timbra l'entrata quando arrivi.",
        tag=TAG_ENTRATA,
        renotify=True,
        urgency="high",
        actions=[
            _azione(
                "entrata",
                "Timbra entrata",
                _action_token(a="entrata", v=str(volontario.pk), s=str(servizio.pk)),
            )
        ],
    )
