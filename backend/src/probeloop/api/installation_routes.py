"""First-run installation and machine settings; provisioning runs as persisted jobs."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, field_validator

from probeloop.api.schemas import JobView
from probeloop.bootstrap import Container
from probeloop.interview.domain.model import Language
from probeloop.speech.audio import to_wav
from probeloop.speech.ports import SpeechError
from probeloop.workspace.execution import execution_tools
from probeloop.workspace.installation import INSTALL_MODEL_JOB, PULL_MODEL_JOB
from probeloop.workspace.service import DataBusyError


class InstallationConfigView(BaseModel):
    completed: bool
    refinement: bool
    ollama_url: str
    limits_url: str


class InstalledModelView(BaseModel):
    id: str
    title: str
    license: str
    source: str
    bytes: int
    state: Literal["missing", "partial", "unverified", "ready"]
    download_available: bool


class ProvisioningView(BaseModel):
    available: bool
    models: list[InstalledModelView]
    error: str | None = None
    free_bytes: int | None = None
    memory_bytes: int | None = None
    cpus: int | None = None
    architecture: str | None = None
    catalog_version: int | None = None


class InstallationView(BaseModel):
    managed: bool
    locked: bool
    config: InstallationConfigView
    provisioning: ProvisioningView
    local_models: dict[str, str]
    jobs: list[JobView] = []


class InstallationChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refinement: bool
    ollama_url: str
    limits_url: str

    @field_validator("ollama_url")
    @classmethod
    def valid_ollama(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("enter the HTTP address of your Ollama server without credentials")
        return value.rstrip("/")

    @field_validator("limits_url")
    @classmethod
    def valid_limits(cls, value: str) -> str:
        if value:
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("enter a public HTTPS model directory without credentials")
        return value.rstrip("/")


async def require_json(request: Request) -> None:
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(415, "content type must be application/json")


def installation_router(container: Container) -> APIRouter:
    router = APIRouter(prefix="/api/installation")
    service = container.installation

    async def idle() -> None:
        try:
            await container.data.ensure_idle()
        except DataBusyError as exc:
            raise HTTPException(409, str(exc)) from exc

    async def view() -> InstallationView:
        try:
            await container.data.ensure_idle()
            locked = False
        except DataBusyError:
            locked = True
        jobs = []
        if service.managed:
            for subject in ("parakeet", "piper-it", "laya", "whisper", *service.local_models):
                history = [
                    job
                    for job in await container.jobs.for_subject(subject)
                    if job.kind in (INSTALL_MODEL_JOB, PULL_MODEL_JOB)
                ]
                if history:
                    jobs.append(JobView.of(max(history, key=lambda job: job.created_at)))
        return InstallationView(**(await service.status()), locked=locked, jobs=jobs)

    @router.get("")
    async def status() -> InstallationView:
        return await view()

    @router.put("", dependencies=[Depends(require_json)])
    async def configure(choice: InstallationChoice) -> InstallationView:
        await idle()
        previous = service.config
        await service.configure(replace(previous, **choice.model_dump()))
        if choice.refinement and not previous.refinement:
            await container.jobs.submit(INSTALL_MODEL_JOB, "whisper")
        return await view()

    @router.post("/models/{identity}", status_code=202, dependencies=[Depends(require_json)])
    async def install(identity: str) -> JobView:
        await idle()
        if identity not in ("parakeet", "piper-it", "laya", "whisper"):
            raise HTTPException(404, "unknown model")
        if identity == "whisper" and not service.config.refinement:
            raise HTTPException(409, "enable second transcription in Settings first")
        return JobView.of(await container.jobs.submit(INSTALL_MODEL_JOB, identity))

    @router.get("/ollama")
    async def ollama_status() -> dict[str, object]:
        return dict(await service.local.status(service.config.ollama_url))

    @router.post("/base", status_code=202, dependencies=[Depends(require_json)])
    async def install_base() -> list[JobView]:
        """The speech components. Laya and Whisper are optional and installed one by one."""
        await idle()
        return [
            JobView.of(await container.jobs.submit(INSTALL_MODEL_JOB, name))
            for name in ("parakeet", "piper-it")
        ]

    @router.post("/ollama/{role}", status_code=202, dependencies=[Depends(require_json)])
    async def pull(role: str) -> JobView:
        await idle()
        if role not in service.local_models:
            raise HTTPException(404, "unknown local model role")
        return JobView.of(await container.jobs.submit(PULL_MODEL_JOB, role))

    @router.post("/complete", dependencies=[Depends(require_json)])
    async def complete() -> InstallationView:
        await idle()
        options = await container.tool_options()
        for role, selected in execution_tools(container.profiles.current).items():
            if not any(o.id == selected and o.available for o in options[role]):
                raise HTTPException(409, "choose an available tool for every role in Settings")
        await service.complete()
        return await view()

    @router.get("/voice-preview")
    async def voice_preview() -> Response:
        await idle()
        # A fixed synthetic phrase; neither arbitrary speech nor user documents leave this route.
        voice = container.sessions.voice
        if voice is None:
            raise HTTPException(409, "speech synthesis is not configured")
        name = voice.voice_for(Language.ITALIAN)
        if name is None:
            raise HTTPException(409, "an Italian voice is not configured")
        try:
            if not (await voice.synthesis_status(name)).ready:
                raise HTTPException(503, "speech synthesis is not ready")
            audio = await voice.tts.synthesize("Benvenuto in ProbeLoop. La voce è pronta.", name)
        except SpeechError as exc:
            raise HTTPException(503, "speech synthesis is not ready") from exc
        return Response(to_wav(audio), media_type="audio/wav")

    return router
