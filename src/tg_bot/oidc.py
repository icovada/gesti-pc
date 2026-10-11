"""Login con Telegram via OpenID Connect (Authorization Code + PKCE).

Vedi https://core.telegram.org/bots/telegram-login. Il client ID è l'ID numerico
del bot; il client secret si ottiene da @BotFather. Gli endpoint vengono letti
dal documento di discovery, l'id_token è verificato con le chiavi pubbliche (JWKS).
"""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import jwt
import requests
from django.conf import settings

ISSUER = "https://oauth.telegram.org"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"
SCOPES = "openid profile"
CACHE_TTL = 3600
HTTP_TIMEOUT = 10

_cache: dict[str, tuple[float, dict]] = {}


class OIDCError(Exception):
    """Login non riuscito; il messaggio è adatto all'utente."""


def client_id() -> str:
    """Client ID configurato, o l'ID del bot (la parte del token prima di ':')."""
    if settings.TELEGRAM_OIDC_CLIENT_ID:
        return settings.TELEGRAM_OIDC_CLIENT_ID
    return (settings.TELEGRAM_BOT_TOKEN or "").split(":", 1)[0]


def is_configured() -> bool:
    return bool(client_id() and settings.TELEGRAM_OIDC_CLIENT_SECRET)


def redirect_uri() -> str:
    """Deve coincidere esattamente con l'URL registrato su @BotFather."""
    return f"{settings.SITE_URL.rstrip('/')}/auth/telegram/callback/"


def _fetch_json(url: str, force: bool = False) -> dict:
    cached = _cache.get(url)
    if cached and not force and cached[0] > time.monotonic():
        return cached[1]
    response = requests.get(url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    _cache[url] = (time.monotonic() + CACHE_TTL, data)
    return data


def _config() -> dict:
    return _fetch_json(DISCOVERY_URL)


def new_login_state() -> dict:
    """Valori casuali di una richiesta di login, da conservare in sessione."""
    return {
        "state": secrets.token_urlsafe(24),
        "nonce": secrets.token_urlsafe(24),
        "verifier": secrets.token_urlsafe(48),
    }


def authorization_url(login_state: dict) -> str:
    challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(login_state["verifier"].encode()).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    params = {
        "response_type": "code",
        "client_id": client_id(),
        "redirect_uri": redirect_uri(),
        "scope": SCOPES,
        "state": login_state["state"],
        "nonce": login_state["nonce"],
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{_config()['authorization_endpoint']}?{urlencode(params)}"


def exchange_code(code: str, verifier: str) -> str:
    """Scambia il codice di autorizzazione con l'id_token."""
    config = _config()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "code_verifier": verifier,
    }
    auth = None
    methods = config.get("token_endpoint_auth_methods_supported", [])
    if "client_secret_basic" in methods or not methods:
        auth = (client_id(), settings.TELEGRAM_OIDC_CLIENT_SECRET)
    else:
        data["client_id"] = client_id()
        data["client_secret"] = settings.TELEGRAM_OIDC_CLIENT_SECRET

    try:
        response = requests.post(
            config["token_endpoint"], data=data, auth=auth, timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        id_token = response.json().get("id_token")
    except (requests.RequestException, ValueError) as e:
        raise OIDCError("Telegram non ha confermato l'accesso. Riprova.") from e
    if not id_token:
        raise OIDCError("Telegram non ha confermato l'accesso. Riprova.")
    return id_token


def _signing_key(id_token: str):
    kid = jwt.get_unverified_header(id_token).get("kid")
    jwks_uri = _config()["jwks_uri"]
    for force in (False, True):  # una chiave sconosciuta forza il refresh (rotazione)
        for key in jwt.PyJWKSet.from_dict(_fetch_json(jwks_uri, force)).keys:
            if kid is None or key.key_id == kid:
                return key
    raise OIDCError("Firma di Telegram non riconosciuta.")


def verify_id_token(id_token: str, nonce: str) -> dict:
    """Verifica firma, emittente, destinatario, scadenza e nonce; restituisce i claim."""
    try:
        key = _signing_key(id_token)
        claims = jwt.decode(
            id_token,
            key=key,
            algorithms=[key.algorithm_name],
            audience=client_id(),
            issuer=_config().get("issuer", ISSUER),
            leeway=60,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError as e:
        raise OIDCError("Accesso Telegram non valido. Riprova.") from e
    if claims.get("nonce") != nonce:
        raise OIDCError("Accesso Telegram non valido. Riprova.")
    try:
        claims["id"] = int(claims["id"])  # ID numerico dell'utente Telegram
    except (KeyError, TypeError, ValueError) as e:
        raise OIDCError("Telegram non ha fornito l'identità dell'utente.") from e
    return claims
