"""Sign in with ChatGPT: OAuth that lets model calls use the user's ChatGPT plan (ADR 0013).

The flow follows OpenAI's documentation for open-source, locally run apps
(https://developers.openai.com/siwc/token-sharing-open-source):

- the first sign-in registers the app dynamically (`dynamic_agent_client`) and the callback
  returns the issued client ID, which every later sign-in, exchange and refresh uses;
- authorization code with PKCE (S256), a fresh state and nonce, and a loopback redirect URI on
  127.0.0.1 whose path is `/auth/callback`;
- the ID token is verified against OpenAI's published keys; plan usage additionally requires the
  granted `chatgpt.tokens.use.direct` scope;
- access tokens last an hour and refresh tokens rotate, so refreshes are serialised.

Tokens are kept in an owner-only file in the data directory. They never reach the browser,
URLs, logs or backups.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from probeloop.ai.ports import UserActionRequiredError

logger = logging.getLogger(__name__)

ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL = f"{ISSUER}/api/accounts/oauth/token"
REVOKE_URL = f"{ISSUER}/api/accounts/oauth/revoke"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
REGISTRATION_CLIENT = "dynamic_agent_client"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = f"openid profile email offline_access resource.invoke {PLAN_SCOPE}"
CALLBACK_PATH = "/auth/callback"
USAGE_URL = "https://chatgpt.com/settings/usage"
_PENDING_TTL_S = 600.0
_REFRESH_MARGIN_S = 120.0
_TERMINAL_REFRESH_ERRORS = frozenset(
    {
        "invalid_grant",
        "invalid_refresh_token",
        "token_expired",
        "refresh_token_expired",
        "refresh_token_invalidated",
        "refresh_token_reused",
    }
)
SIGN_IN_AGAIN = "sign in with ChatGPT again in Settings"


class SignInError(Exception):
    """A sign-in attempt failed. `reason` is a short code the UI can show in its own words."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class AccountStatus:
    signed_in: bool
    email: str | None = None
    # The plan scope was granted: model calls may use the ChatGPT plan.
    plan_usage: bool = False


class ChatGptAccount(Protocol):
    def status(self) -> AccountStatus: ...

    def begin(self, redirect_uri: str) -> str:
        """Start a sign-in; returns the URL to open in the browser."""
        ...

    async def complete(self, query: Mapping[str, str]) -> AccountStatus: ...

    async def access_token(self, *, refresh: bool = False) -> str: ...

    async def sign_out(self) -> None: ...


@dataclass(frozen=True, slots=True)
class _Pending:
    verifier: str
    nonce: str
    redirect_uri: str
    client_id: str
    created: float


class ChatGptAuth:
    def __init__(
        self,
        directory: Path,
        *,
        app_name: str = "ProbeLoop",
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._directory = directory
        self._app_name = app_name
        self._clock = clock
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0), transport=transport)
        self._pending: dict[str, _Pending] = {}
        self._lock = asyncio.Lock()
        self._jwks: dict[str, Any] | None = None
        self._credentials: dict[str, Any] = self._read()

    @property
    def _path(self) -> Path:
        return self._directory / "credentials.json"

    def status(self) -> AccountStatus:
        signed_in = bool(self._credentials.get("refresh_token"))
        return AccountStatus(
            signed_in=signed_in,
            email=self._credentials.get("email") if signed_in else None,
            plan_usage=signed_in and PLAN_SCOPE in self._credentials.get("scope", "").split(),
        )

    def begin(self, redirect_uri: str) -> str:
        now = self._clock()
        self._pending = {k: v for k, v in self._pending.items() if now - v.created < _PENDING_TTL_S}
        verifier = secrets.token_urlsafe(64)
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        client_id = self._credentials.get("client_id") or REGISTRATION_CLIENT
        self._pending[state] = _Pending(verifier, nonce, redirect_uri, client_id, now)
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "resource": RESOURCE,
            "state": state,
            "nonce": nonce,
            "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
            "code_challenge_method": "S256",
            "ext_agent_host_id": self._host_id(),
        }
        if client_id == REGISTRATION_CLIENT:
            params["agent_name_hint"] = self._app_name
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def complete(self, query: Mapping[str, str]) -> AccountStatus:
        if query.get("error"):
            raise SignInError("denied" if query["error"] == "access_denied" else "failed")
        pending = self._pending.pop(query.get("state", ""), None)
        if pending is None or self._clock() - pending.created >= _PENDING_TTL_S:
            raise SignInError("expired")
        client_id = query.get("client_id") or pending.client_id
        if client_id == REGISTRATION_CLIENT or not query.get("code"):
            raise SignInError("failed")
        tokens = await self._token_request(
            {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": query["code"],
                "code_verifier": pending.verifier,
                "redirect_uri": pending.redirect_uri,
                "resource": RESOURCE,
            }
        )
        if tokens is None or not tokens.get("refresh_token") or not tokens.get("id_token"):
            raise SignInError("failed")
        try:
            claims = await self._verified_claims(tokens["id_token"], client_id, pending.nonce)
        except (ValueError, KeyError, InvalidSignature, httpx.HTTPError):
            logger.warning("ChatGPT sign-in returned an ID token that did not verify")
            raise SignInError("failed") from None
        async with self._lock:
            self._store(client_id, tokens, claims)
        return self.status()

    async def access_token(self, *, refresh: bool = False) -> str:
        async with self._lock:
            if not self.status().signed_in:
                raise UserActionRequiredError(SIGN_IN_AGAIN)
            if not self.status().plan_usage:
                raise UserActionRequiredError(
                    "allow ProbeLoop to use your ChatGPT plan in Settings"
                )
            expires = float(self._credentials.get("expires_at", 0))
            if refresh or expires - _REFRESH_MARGIN_S <= self._clock():
                await self._refresh()
            return str(self._credentials["access_token"])

    async def sign_out(self) -> None:
        async with self._lock:
            token = self._credentials.get("refresh_token")
            client_id = self._credentials.get("client_id")
            if token and client_id:
                await self._revoke(str(token), str(client_id))
            # The issued client ID stays: revoking does not delete the registration, and later
            # sign-ins reuse it.
            self._credentials = {"client_id": client_id} if client_id else {}
            await asyncio.to_thread(self._write)

    async def _refresh(self) -> None:
        client_id = str(self._credentials["client_id"])
        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": self._credentials["refresh_token"],
            "resource": RESOURCE,
        }
        try:
            response = await self._client.post(TOKEN_URL, data=data)
        except httpx.HTTPError as exc:
            # A network failure is not a reason to discard credentials.
            raise UserActionRequiredError(
                "ChatGPT sign-in could not be renewed; try again"
            ) from exc
        body = _json(response)
        if response.status_code >= 400:
            code = str(body.get("error") or "")
            if code in _TERMINAL_REFRESH_ERRORS:
                logger.warning("ChatGPT refresh token is no longer valid", extra={"code": code})
                self._credentials = {"client_id": client_id}
                await asyncio.to_thread(self._write)
                raise UserActionRequiredError(SIGN_IN_AGAIN)
            raise UserActionRequiredError("ChatGPT sign-in could not be renewed; try again")
        self._store(client_id, body, None)

    async def _revoke(self, token: str, client_id: str) -> None:
        for _ in range(2):
            try:
                response = await self._client.post(
                    REVOKE_URL,
                    data={
                        "token": token,
                        "token_type_hint": "refresh_token",
                        "client_id": client_id,
                    },
                )
            except httpx.HTTPError:
                continue
            if response.status_code < 500:
                return
        logger.warning("ChatGPT token revocation did not complete; local tokens are removed")

    async def _token_request(self, data: dict[str, str]) -> dict[str, Any] | None:
        try:
            response = await self._client.post(TOKEN_URL, data=data)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            logger.warning(
                "ChatGPT code exchange failed",
                extra={"status": response.status_code, "code": _json(response).get("error")},
            )
            return None
        return _json(response)

    async def _verified_claims(self, token: str, client_id: str, nonce: str) -> dict[str, Any]:
        if self._jwks is None:
            response = await self._client.get(JWKS_URL)
            response.raise_for_status()
            self._jwks = _json(response)
        claims = verify_id_token(token, self._jwks, now=self._clock())
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if claims.get("iss") != ISSUER or client_id not in audiences:
            raise ValueError("unexpected issuer or audience")
        if claims.get("nonce") != nonce:
            raise ValueError("nonce mismatch")
        return claims

    def _store(
        self, client_id: str, tokens: Mapping[str, Any], claims: Mapping[str, Any] | None
    ) -> None:
        credentials = dict(self._credentials) if claims is None else {}
        credentials.update(
            {
                "client_id": client_id,
                "access_token": tokens["access_token"],
                # Refresh tokens rotate; keep the previous one if a response omits it.
                "refresh_token": tokens.get("refresh_token") or credentials.get("refresh_token"),
                "expires_at": self._clock() + float(tokens.get("expires_in", 3600)),
                "scope": tokens.get("scope") or credentials.get("scope", ""),
            }
        )
        if tokens.get("id_token"):
            credentials["id_token"] = tokens["id_token"]
        if claims is not None:
            credentials["sub"] = claims.get("sub")
            credentials["email"] = claims.get("email")
        self._credentials = credentials
        self._write()

    def _host_id(self) -> str:
        """An opaque, persistent identifier of this installation (not a credential)."""
        path = self._directory / "host-id"
        try:
            return path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            host_id = f"urn:uuid:{uuid.uuid4()}"
            self._directory.mkdir(parents=True, exist_ok=True)
            path.write_text(host_id, encoding="utf-8")
            return host_id

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            logger.warning("unreadable ChatGPT credentials; sign in again")
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(self._credentials, file)
        temporary.replace(self._path)


def verify_id_token(token: str, jwks: Mapping[str, Any], *, now: float) -> dict[str, Any]:
    """The claims of an RS256 ID token whose signature and expiry are valid."""
    header_part, payload_part, signature_part = token.split(".")
    header = json.loads(_unb64url(header_part))
    if header.get("alg") != "RS256":
        raise ValueError("unsupported signing algorithm")
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if key is None:
        raise ValueError("unknown signing key")
    public_key = rsa.RSAPublicNumbers(
        int.from_bytes(_unb64url(key["e"]), "big"), int.from_bytes(_unb64url(key["n"]), "big")
    ).public_key()
    public_key.verify(
        _unb64url(signature_part),
        f"{header_part}.{payload_part}".encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    claims: dict[str, Any] = json.loads(_unb64url(payload_part))
    if float(claims.get("exp", 0)) <= now:
        raise ValueError("expired ID token")
    return claims


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
