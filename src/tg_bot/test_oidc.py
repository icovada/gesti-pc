import json
import time
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from tg_bot import oidc
from tg_bot.models import TelegramUser
from volontario.models import Volontario

VALID_CF = "RSSMRA90A01H501W"
CLIENT_ID = "123456"
SITE = "https://gestipc.example.it"

PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key()))
JWKS = {"keys": [{**JWK, "kid": "k1", "alg": "RS256", "use": "sig"}]}
DISCOVERY = {
    "issuer": oidc.ISSUER,
    "authorization_endpoint": f"{oidc.ISSUER}/auth",
    "token_endpoint": f"{oidc.ISSUER}/token",
    "jwks_uri": f"{oidc.ISSUER}/.well-known/jwks.json",
    "token_endpoint_auth_methods_supported": ["client_secret_basic"],
}


def fake_fetch_json(url, force=False):
    return JWKS if url == DISCOVERY["jwks_uri"] else DISCOVERY


def make_id_token(nonce, key=PRIVATE_KEY, **overrides):
    now = int(time.time())
    claims = {
        "iss": oidc.ISSUER,
        "aud": CLIENT_ID,
        "sub": "opaque-subject",
        "iat": now,
        "exp": now + 300,
        "nonce": nonce,
        "id": 42,
        "name": "Mario Rossi",
        **overrides,
    }
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "k1"})


@override_settings(
    SITE_URL=SITE,
    TELEGRAM_BOT_TOKEN=f"{CLIENT_ID}:TOKEN",
    TELEGRAM_OIDC_CLIENT_ID="",
    TELEGRAM_OIDC_CLIENT_SECRET="secret",
)
@patch("tg_bot.oidc._fetch_json", side_effect=fake_fetch_json)
class TelegramOIDCLoginTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mario")
        volontario = Volontario.objects.create(
            codice_fiscale=VALID_CF, nome="Mario", cognome="Rossi", user=self.user
        )
        TelegramUser.objects.create(telegram_id=42, volontario=volontario)

    def start_login(self, next_url=None):
        url = reverse("login") + (f"?next={next_url}" if next_url else "")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        params = parse_qs(urlparse(response["Location"]).query)
        return {k: v[0] for k, v in params.items()}

    def callback(self, params, id_token):
        token_response = MagicMock()
        token_response.json.return_value = {"id_token": id_token}
        with patch("tg_bot.oidc.requests.post", return_value=token_response) as post:
            response = self.client.get(
                reverse("telegram_callback"),
                {"code": "the-code", "state": params["state"]},
            )
        return response, post

    def test_authorization_request(self, _fetch):
        params = self.start_login()
        self.assertEqual(params["client_id"], CLIENT_ID)  # derived from bot token
        self.assertEqual(params["redirect_uri"], f"{SITE}/auth/telegram/callback/")
        self.assertEqual(params["response_type"], "code")
        self.assertEqual(params["code_challenge_method"], "S256")
        self.assertIn("openid", params["scope"])

    def test_successful_login(self, _fetch):
        params = self.start_login(next_url="/app/report/ore/")
        response, post = self.callback(params, make_id_token(params["nonce"]))

        self.assertRedirects(
            response, "/app/report/ore/", fetch_redirect_response=False
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        sent = post.call_args.kwargs
        self.assertEqual(sent["auth"], (CLIENT_ID, "secret"))
        self.assertEqual(sent["data"]["code"], "the-code")
        self.assertIn("code_verifier", sent["data"])

    def test_rejects_forged_signature(self, _fetch):
        params = self.start_login()
        response, _ = self.callback(
            params, make_id_token(params["nonce"], key=OTHER_KEY)
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_rejects_wrong_audience_and_nonce(self, _fetch):
        for token_kwargs in ({"aud": "999"}, {"nonce": "replayed"}):
            params = self.start_login()
            id_token = make_id_token(**{"nonce": params["nonce"], **token_kwargs})
            self.callback(params, id_token)
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_rejects_state_mismatch(self, _fetch):
        params = self.start_login()
        response, post = self.callback(
            {**params, "state": "attacker"}, make_id_token(params["nonce"])
        )
        post.assert_not_called()
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unlinked_telegram_account(self, _fetch):
        params = self.start_login()
        response, _ = self.callback(params, make_id_token(params["nonce"], id=99))
        self.assertNotIn("_auth_user_id", self.client.session)
        landing = self.client.get(response["Location"])
        self.assertContains(landing, "non è collegato a un volontario")

    @override_settings(TELEGRAM_OIDC_CLIENT_SECRET="")
    def test_not_configured(self, _fetch):
        response = self.client.get(reverse("login"))
        self.assertRedirects(response, "/", fetch_redirect_response=False)


class LandingTests(TestCase):
    def test_landing_has_login_button(self):
        response = self.client.get("/?next=/app/report/ore/")
        self.assertContains(response, "Accedi con Telegram")
        self.assertContains(response, "/login/?next=%2Fapp%2Freport%2Fore%2F")
