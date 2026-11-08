"""Sign in with ChatGPT against a scripted OpenAI authorization server; nothing leaves the test."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import stat
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from probeloop.ai.chatgpt_auth import (
    AUTHORIZE_URL,
    ISSUER,
    JWKS_URL,
    PLAN_SCOPE,
    REVOKE_URL,
    TOKEN_URL,
    ChatGptAuth,
    SignInError,
)
from probeloop.ai.ports import UserActionRequiredError

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
CLIENT = "oaiapp_synthetic"
REDIRECT = "http://127.0.0.1:8000/auth/callback"
GRANTED = f"openid profile email offline_access resource.invoke {PLAN_SCOPE}"


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def jwks() -> dict[str, Any]:
    numbers = KEY.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "k1",
                "n": b64(numbers.n.to_bytes(256, "big")),
                "e": b64(numbers.e.to_bytes(3, "big")),
            }
        ]
    }


def id_token(claims: dict[str, Any], key: rsa.RSAPrivateKey = KEY) -> str:
    header = b64(json.dumps({"alg": "RS256", "kid": "k1"}).encode())
    payload = b64(json.dumps(claims).encode())
    signature = key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{b64(signature)}"


class Server:
    """The token, key and revocation endpoints, recording the forms they receive."""

    def __init__(self) -> None:
        self.forms: list[dict[str, str]] = []
        self.nonce = ""
        self.scope = GRANTED
        self.refresh_error: str | None = None
        self.refreshes = 0
        self.key: rsa.RSAPrivateKey = KEY
        self.now = 1_000_000.0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) == JWKS_URL:
            return httpx.Response(200, json=jwks())
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.forms.append(form)
        if str(request.url) == REVOKE_URL:
            return httpx.Response(200)
        assert str(request.url) == TOKEN_URL
        if form["grant_type"] == "refresh_token":
            if self.refresh_error:
                return httpx.Response(400, json={"error": self.refresh_error})
            self.refreshes += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"access-{self.refreshes + 1}",
                    "refresh_token": f"refresh-{self.refreshes + 1}",
                    "expires_in": 3600,
                },
            )
        claims = {
            "iss": ISSUER,
            "aud": CLIENT,
            "sub": "user-1",
            "email": "synthetic@example.test",
            "exp": self.now + 3600,
            "nonce": self.nonce,
        }
        return httpx.Response(
            200,
            json={
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "id_token": id_token(claims, self.key),
                "expires_in": 3600,
                "scope": self.scope,
            },
        )


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def auth(tmp_path: Path, server: Server, clock: Clock) -> ChatGptAuth:
    return ChatGptAuth(tmp_path / "chatgpt", transport=httpx.MockTransport(server), clock=clock)


async def sign_in(account: ChatGptAuth, server: Server) -> dict[str, str]:
    url = account.begin(REDIRECT)
    params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    server.nonce = params["nonce"]
    await account.complete({"code": "code-1", "state": params["state"], "client_id": CLIENT})
    return params


@pytest.fixture
def server() -> Server:
    return Server()


@pytest.fixture
def clock() -> Clock:
    return Clock()


async def test_the_first_sign_in_registers_the_app_with_pkce(
    tmp_path: Path, server: Server, clock: Clock
) -> None:
    account = auth(tmp_path, server, clock)
    url = account.begin(REDIRECT)
    assert url.startswith(AUTHORIZE_URL + "?")
    params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    assert params["client_id"] == "dynamic_agent_client"
    assert params["agent_name_hint"] == "ProbeLoop"
    assert params["redirect_uri"] == REDIRECT
    assert params["code_challenge_method"] == "S256"
    assert params["resource"] == "https://api.openai.com/v1"
    assert PLAN_SCOPE in params["scope"].split()
    assert params["ext_agent_host_id"].startswith("urn:uuid:")
    server.nonce = params["nonce"]
    status = await account.complete({"code": "c", "state": params["state"], "client_id": CLIENT})
    assert (status.signed_in, status.email, status.plan_usage) == (
        True,
        "synthetic@example.test",
        True,
    )
    exchange = server.forms[-1]
    assert exchange["client_id"] == CLIENT  # the issued client, not the registration entrypoint
    assert exchange["redirect_uri"] == REDIRECT
    assert len(exchange["code_verifier"]) >= 43
    # Later sign-ins reuse the issued client and the same host identifier.
    again = {k: v[0] for k, v in parse_qs(urlsplit(account.begin(REDIRECT)).query).items()}
    assert again["client_id"] == CLIENT
    assert "agent_name_hint" not in again
    assert again["ext_agent_host_id"] == params["ext_agent_host_id"]


async def test_credentials_are_kept_in_an_owner_only_file(
    tmp_path: Path, server: Server, clock: Clock
) -> None:
    await sign_in(auth(tmp_path, server, clock), server)
    path = tmp_path / "chatgpt" / "credentials.json"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    restored = auth(tmp_path, server, clock)
    assert restored.status().email == "synthetic@example.test"
    assert await restored.access_token() == "access-1"


@pytest.mark.parametrize(
    "callback",
    [
        {"error": "access_denied", "state": "x"},
        {"code": "c", "state": "unknown", "client_id": CLIENT},
    ],
)
async def test_denied_or_unknown_callbacks_are_refused(
    tmp_path: Path, server: Server, clock: Clock, callback: dict[str, str]
) -> None:
    account = auth(tmp_path, server, clock)
    account.begin(REDIRECT)
    with pytest.raises(SignInError):
        await account.complete(callback)
    assert not account.status().signed_in
    assert server.forms == []


async def test_an_id_token_that_does_not_verify_is_rejected(
    tmp_path: Path, server: Server, clock: Clock
) -> None:
    server.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(SignInError, match="failed"):
        await sign_in(auth(tmp_path, server, clock), server)
    server.key = KEY
    account = auth(tmp_path, server, clock)
    url = account.begin(REDIRECT)
    state = parse_qs(urlsplit(url).query)["state"][0]
    server.nonce = "another nonce"
    with pytest.raises(SignInError):
        await account.complete({"code": "c", "state": state, "client_id": CLIENT})
    assert not account.status().signed_in


async def test_without_the_plan_scope_the_plan_is_not_used(
    tmp_path: Path, server: Server, clock: Clock
) -> None:
    server.scope = "openid profile email offline_access"
    account = auth(tmp_path, server, clock)
    await sign_in(account, server)
    assert account.status().signed_in
    assert not account.status().plan_usage
    with pytest.raises(UserActionRequiredError):
        await account.access_token()


async def test_tokens_refresh_once_before_expiry_and_rotate(
    tmp_path: Path, server: Server, clock: Clock
) -> None:
    account = auth(tmp_path, server, clock)
    await sign_in(account, server)
    clock.now += 3550  # inside the refresh margin
    tokens = await asyncio.gather(account.access_token(), account.access_token())
    assert tokens == ["access-2", "access-2"]
    assert server.refreshes == 1
    refresh = server.forms[-1]
    assert (refresh["grant_type"], refresh["client_id"], refresh["refresh_token"]) == (
        "refresh_token",
        CLIENT,
        "refresh-1",
    )
    assert "scope" not in refresh
    assert await account.access_token(refresh=True) == "access-3"
    assert server.forms[-1]["refresh_token"] == "refresh-2"  # the rotated token


async def test_an_unusable_refresh_token_requires_signing_in_again(
    tmp_path: Path, server: Server, clock: Clock
) -> None:
    account = auth(tmp_path, server, clock)
    await sign_in(account, server)
    server.refresh_error = "refresh_token_reused"
    with pytest.raises(UserActionRequiredError, match="sign in with ChatGPT again"):
        await account.access_token(refresh=True)
    assert not account.status().signed_in
    assert "oaiapp" in account.begin(REDIRECT)  # the registration is kept


async def test_a_network_failure_keeps_the_credentials(tmp_path: Path, clock: Clock) -> None:
    server = Server()
    account = auth(tmp_path, server, clock)
    await sign_in(account, server)

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic", request=request)

    offline = ChatGptAuth(
        tmp_path / "chatgpt", transport=httpx.MockTransport(unreachable), clock=clock
    )
    with pytest.raises(UserActionRequiredError, match="could not be renewed"):
        await offline.access_token(refresh=True)
    assert offline.status().signed_in


async def test_signing_out_revokes_the_refresh_token(
    tmp_path: Path, server: Server, clock: Clock
) -> None:
    account = auth(tmp_path, server, clock)
    await sign_in(account, server)
    await account.sign_out()
    revoke = server.forms[-1]
    assert revoke == {
        "token": "refresh-1",
        "token_type_hint": "refresh_token",
        "client_id": CLIENT,
    }
    assert not account.status().signed_in
    stored = json.loads((tmp_path / "chatgpt" / "credentials.json").read_text())
    assert stored == {"client_id": CLIENT}
