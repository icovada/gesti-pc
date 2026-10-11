"""Validazione dei dati di avvio (initData) di una Telegram Mini App.

Vedi https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

# initData più vecchi di così vengono rifiutati (protezione da replay).
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age: int = DEFAULT_MAX_AGE_SECONDS,
    now: float | None = None,
) -> dict | None:
    """Verifica la firma di initData e restituisce l'oggetto `user`, o None se non valido."""
    if not init_data or not bot_token:
        return None

    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None

    received_hash = fields.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        return None

    try:
        auth_date = int(fields.get("auth_date", "0"))
    except ValueError:
        return None
    if (now if now is not None else time.time()) - auth_date > max_age:
        return None

    try:
        user = json.loads(fields.get("user", ""))
    except ValueError:
        return None
    if not isinstance(user, dict) or "id" not in user:
        return None
    return user
