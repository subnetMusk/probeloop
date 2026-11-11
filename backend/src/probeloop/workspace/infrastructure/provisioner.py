"""Internal model installer. It writes only catalogued files, never controls Docker."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import ipaddress
import json
import os
import platform
import shutil
import socket
import time
from collections.abc import AsyncIterator
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict


def catalog() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        files(__package__).joinpath("model_catalog.json").read_text()
    )
    return value


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_download_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("model downloads require a public HTTPS URL without credentials")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("model downloads cannot access private or loopback addresses")


class InstallBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limits_url: str = ""


class Provisioner:
    def __init__(
        self,
        root: Path,
        *,
        manifest: dict[str, Any] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        validate_urls: bool = True,
    ) -> None:
        self.root = root.resolve()
        self.manifest = manifest or catalog()
        self.models = {m["id"]: m for m in self.manifest["models"]}
        self.transport = transport
        self.validate_urls = validate_urls
        self.lock = asyncio.Lock()

    def path(self, relative: str) -> Path:
        target = self.root / relative
        if not target.resolve().is_relative_to(self.root) or target == self.root:
            raise ValueError("invalid catalog path")
        return target

    def signature(self, model: dict[str, Any]) -> dict[str, list[int]]:
        return {
            asset["path"]: [
                self.path(asset["path"]).stat().st_size,
                self.path(asset["path"]).stat().st_mtime_ns,
            ]
            for asset in model["files"]
        }

    def status(self) -> dict[str, Any]:
        models = []
        for model in self.models.values():
            state = "missing"
            present = sum(
                self.path(a["path"]).is_file() and self.path(a["path"]).stat().st_size == a["size"]
                for a in model["files"]
            )
            if present:
                state = "unverified" if present == len(model["files"]) else "partial"
            if state == "unverified":
                try:
                    receipt = json.loads(self.path(f".installation/{model['id']}.json").read_text())
                    if receipt == self.signature(model):
                        state = "ready"
                except (OSError, ValueError):
                    pass
            models.append(
                {
                    "id": model["id"],
                    "title": model["title"],
                    "license": model["license"],
                    "source": model["source"],
                    "bytes": sum(a["size"] for a in model["files"]),
                    "state": state,
                    "download_available": all(a["url"] for a in model["files"]),
                }
            )
        memory = None
        with contextlib.suppress(ValueError, OSError, AttributeError):
            memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return {
            "available": True,
            "catalog_version": self.manifest["version"],
            "models": models,
            "free_bytes": shutil.disk_usage(self.root).free,
            "memory_bytes": memory,
            "cpus": os.cpu_count(),
            "architecture": platform.machine(),
        }

    async def valid(self, path: Path, asset: dict[str, Any]) -> bool:
        def check() -> bool:
            return (
                path.is_file()
                and path.stat().st_size == asset["size"]
                and checksum(path) == asset["sha256"]
            )

        return await asyncio.to_thread(check)

    async def response(self, client: httpx.AsyncClient, url: str, offset: int) -> httpx.Response:
        for _ in range(8):
            if self.validate_urls:
                await asyncio.to_thread(validate_download_url, url)
            response = await client.send(
                client.build_request("GET", url, headers={"Range": f"bytes={offset}-"}),
                stream=True,
            )
            if response.is_redirect:
                next_url = str(response.url.join(response.headers["location"]))
                await response.aclose()
                url = next_url
                continue
            response.raise_for_status()
            return response
        raise ValueError("too many model download redirects")

    async def install(self, identity: str, limits_url: str) -> AsyncIterator[dict[str, Any]]:
        model = self.models[identity]
        async with self.lock:
            pending = []
            for asset in model["files"]:
                checking = asyncio.create_task(self.valid(self.path(asset["path"]), asset))
                try:
                    while not checking.done():
                        await asyncio.wait({checking}, timeout=5)
                        yield {"progress": 0.0, "message": "Checking installed model files"}
                    valid = await checking
                finally:
                    if not checking.done():
                        checking.cancel()
                if not valid:
                    pending.append(asset)
            required = sum(a["size"] for a in pending)
            staging = self.path(f".installation/partial/{identity}")
            staging.mkdir(parents=True, exist_ok=True)
            existing = sum(
                min((staging / str(index)).stat().st_size, a["size"])
                for index, a in enumerate(model["files"])
                if a in pending and (staging / str(index)).is_file()
            )
            if shutil.disk_usage(self.root).free < required - existing + 20_000_000:
                raise ValueError("not enough space in Docker's model volume")
            total = sum(a["size"] for a in model["files"])
            completed = total - required
            async with httpx.AsyncClient(transport=self.transport, timeout=120) as client:
                for index, asset in enumerate(model["files"]):
                    if asset not in pending:
                        continue
                    url = asset["url"]
                    if not url:
                        if not limits_url:
                            raise ValueError(
                                "configure the published Laya model URL in Settings first"
                            )
                        suffix = asset["path"].removeprefix("stated-limits/v1/")
                        url = f"{limits_url.rstrip('/')}/{suffix}"
                    partial = staging / str(index)
                    if not await self.valid(partial, asset):
                        offset = partial.stat().st_size if partial.exists() else 0
                        if offset >= asset["size"]:
                            partial.unlink()
                            offset = 0
                        response = await self.response(client, url, offset)
                        try:
                            if response.status_code == 206:
                                if not response.headers.get("content-range", "").startswith(
                                    f"bytes {offset}-"
                                ):
                                    raise ValueError("invalid resumed model download")
                            else:
                                offset = 0
                            received = offset
                            reported = time.monotonic()
                            with partial.open("ab" if offset else "wb") as stream:
                                async for chunk in response.aiter_bytes(262144):
                                    received += len(chunk)
                                    if received > asset["size"]:
                                        raise ValueError("model download exceeds its approved size")
                                    stream.write(chunk)
                                    if time.monotonic() - reported > 0.3:
                                        yield {
                                            "progress": (completed + received) / total,
                                            "message": "Downloading verified model files",
                                        }
                                        reported = time.monotonic()
                        finally:
                            await response.aclose()
                        if not await self.valid(partial, asset):
                            if partial.exists() and partial.stat().st_size == asset["size"]:
                                partial.unlink()
                            raise ValueError(
                                "model checksum or size mismatch; try the download again"
                            )
                    completed += asset["size"]
                    yield {"progress": completed / total, "message": "Verifying model files"}
            # Publish only after every pending file passed its size and checksum checks.
            for index, asset in enumerate(model["files"]):
                if asset in pending:
                    target = self.path(asset["path"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    (staging / str(index)).replace(target)
            reference = model.get("reference")
            if reference:
                target = self.path(reference["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(".tmp")
                temporary.write_text(reference["value"])
                temporary.replace(target)
            receipt = self.path(f".installation/{identity}.json")
            receipt.with_suffix(".tmp").write_text(json.dumps(self.signature(model)))
            receipt.with_suffix(".tmp").replace(receipt)
            yield {"progress": 1.0, "done": True, "message": "Model installed and verified"}


def create_provisioner_app(provisioner: Provisioner) -> FastAPI:
    app = FastAPI(title="ProbeLoop model provisioner", docs_url=None, redoc_url=None)

    @app.get("/status")
    async def status() -> dict[str, Any]:
        return provisioner.status()

    @app.post("/install/{identity}")
    async def install(identity: str, body: InstallBody) -> StreamingResponse:
        if identity not in provisioner.models:
            raise HTTPException(404, "unknown model")

        async def events() -> AsyncIterator[str]:
            try:
                async for item in provisioner.install(identity, body.limits_url):
                    yield json.dumps(item) + "\n"
            except (OSError, ValueError, httpx.HTTPError) as exc:
                # Do not expose signed CDN URLs or HTTP request headers in job errors.
                message = (
                    str(exc) if isinstance(exc, ValueError) else "model download failed; try again"
                )
                yield json.dumps({"error": message}) + "\n"

        return StreamingResponse(events(), media_type="application/x-ndjson")

    return app


def main() -> None:
    root = Path("/models")
    # A fresh named volume may be owned by root. Only initialise the installer-owned paths,
    # then drop privileges before accepting requests; never recursively chown user files.
    if os.getuid() == 0:
        root.mkdir(exist_ok=True)
        directories = {root, root / ".installation"}
        for model in catalog()["models"]:
            names = [asset["path"] for asset in model["files"]]
            if model.get("reference"):
                names.append(model["reference"]["path"])
            for name in names:
                for directory in (root / name).parents:
                    if directory == root:
                        break
                    if not directory.resolve().is_relative_to(root):
                        raise ValueError("invalid catalog directory")
                    directories.add(directory)
        for directory in directories:
            if directory.exists():
                if directory.is_symlink():
                    raise ValueError("catalog directories cannot be symlinks")
                os.chown(directory, 1000, 1000)
        os.setgroups([])
        os.setgid(1000)
        os.setuid(1000)
    (root / ".installation").mkdir(exist_ok=True)
    from probeloop.bootstrap import build_provisioner

    uvicorn.run(
        create_provisioner_app(build_provisioner(root)),
        host="0.0.0.0",  # noqa: S104 - internal Compose service, never published
        port=8000,
        access_log=False,
    )


if __name__ == "__main__":
    main()
