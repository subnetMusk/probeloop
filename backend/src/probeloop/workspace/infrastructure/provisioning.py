"""HTTP adapters for the private model provisioner and Ollama's model-management API."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from probeloop.platform.jobs import Progress
from probeloop.workspace.installation import ProvisioningError


class HttpModelInstaller:
    def __init__(self, url: str | None, *, transport: httpx.AsyncBaseTransport | None = None):
        self._url = url
        self._transport = transport

    async def status(self) -> Mapping[str, Any]:
        if self._url is None:
            raise ProvisioningError("model provisioning is not configured")
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=5) as client:
                response = await client.get(f"{self._url}/status")
                response.raise_for_status()
                value: dict[str, Any] = response.json()
                return value
        except (httpx.HTTPError, ValueError) as exc:
            raise ProvisioningError("model provisioning is unavailable") from exc

    async def install(self, model: str, limits_url: str, progress: Progress) -> None:
        if self._url is None:
            raise ProvisioningError("model provisioning is not configured")
        try:
            async with (
                httpx.AsyncClient(transport=self._transport, timeout=120) as client,
                client.stream(
                    "POST", f"{self._url}/install/{model}", json={"limits_url": limits_url}
                ) as response,
            ):
                response.raise_for_status()
                done = False
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    value = json.loads(line)
                    if value.get("error"):
                        raise ProvisioningError(str(value["error"]))
                    done = bool(value.get("done"))
                    await progress(float(value.get("progress", 0)), value.get("message"))
                if not done:
                    raise ProvisioningError("model download was interrupted; try again")
        except (httpx.HTTPError, ValueError) as exc:
            raise ProvisioningError("model download was interrupted; try again") from exc


class OllamaModelManager:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport

    async def status(self, url: str) -> Mapping[str, Any]:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=3) as client:
                response = await client.get(f"{url.rstrip('/')}/api/tags")
                response.raise_for_status()
                return {"available": True, "models": response.json().get("models", [])}
        except (httpx.HTTPError, ValueError):
            return {"available": False, "models": []}

    async def pull(self, url: str, model: str, progress: Progress) -> None:
        try:
            async with (
                httpx.AsyncClient(transport=self._transport, timeout=120) as client,
                client.stream(
                    "POST", f"{url.rstrip('/')}/api/pull", json={"model": model, "stream": True}
                ) as response,
            ):
                response.raise_for_status()
                done = False
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    item = json.loads(line)
                    if item.get("error"):
                        raise ProvisioningError("Ollama could not download the model")
                    done = item.get("status") == "success"
                    # Ollama reports progress per layer, rather than for the whole model.
                    ratio = item.get("completed", 0) / max(item.get("total", 1), 1)
                    await progress(1.0 if done else min(ratio, 0.99), item.get("status"))
                if not done:
                    raise ProvisioningError("Ollama download was interrupted; try again")
        except (httpx.HTTPError, ValueError) as exc:
            raise ProvisioningError(
                "Ollama is unavailable; check its connection and try again"
            ) from exc
