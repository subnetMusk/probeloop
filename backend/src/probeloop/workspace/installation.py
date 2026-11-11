"""Machine installation settings and provisioning use cases, independent of HTTP and Docker."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any, Protocol

from probeloop.platform.jobs import Job, JobError, Progress

INSTALL_MODEL_JOB = "install_model"
PULL_MODEL_JOB = "pull_local_model"


@dataclass(frozen=True, slots=True)
class InstallationConfig:
    completed: bool = False
    refinement: bool = False
    ollama_url: str = "http://host.docker.internal:11434"
    limits_url: str = ""


class InstallationRepository(Protocol):
    def read(self) -> InstallationConfig: ...

    def save(self, config: InstallationConfig) -> None: ...


class ProvisioningError(RuntimeError):
    """An installation operation could not complete; the current installation is preserved."""


class ModelInstaller(Protocol):
    async def status(self) -> Mapping[str, Any]: ...

    async def install(self, model: str, limits_url: str, progress: Progress) -> None: ...


class LocalModelManager(Protocol):
    async def status(self, url: str) -> Mapping[str, Any]: ...

    async def pull(self, url: str, model: str, progress: Progress) -> None: ...


class InstallationService:
    def __init__(
        self,
        repository: InstallationRepository,
        installer: ModelInstaller,
        local: LocalModelManager,
        *,
        managed: bool,
        local_models: Mapping[str, str],
        apply: Callable[[InstallationConfig], Awaitable[None]],
        reload_models: Callable[[], Awaitable[None]],
    ) -> None:
        self.repository = repository
        self.installer = installer
        self.local = local
        self.managed = managed
        self.local_models = dict(local_models)
        self._apply = apply
        self._reload = reload_models

    @property
    def config(self) -> InstallationConfig:
        return self.repository.read()

    async def configure(self, config: InstallationConfig) -> None:
        # The API's mutation lock and idle guard protect this operation and its consumers.
        await self._apply(config)
        self.repository.save(config)

    async def complete(self) -> None:
        await self.configure(replace(self.config, completed=True))

    async def status(self) -> dict[str, Any]:
        try:
            provision = dict(await self.installer.status())
        except ProvisioningError:
            provision = {"available": False, "models": [], "error": "provisioner_unavailable"}
        return {
            "managed": self.managed,
            "config": asdict(self.config),
            "provisioning": provision,
            "local_models": self.local_models,
        }

    async def install(self, job: Job, progress: Progress) -> Mapping[str, Any]:
        try:
            await self.installer.install(job.subject_id, self.config.limits_url, progress)
            await self._reload()
        except ProvisioningError as exc:
            raise JobError(str(exc)) from exc
        return {"model": job.subject_id, "verified": True}

    async def pull(self, job: Job, progress: Progress) -> Mapping[str, Any]:
        model = self.local_models.get(job.subject_id)
        if model is None:
            raise JobError("unsupported local model role")
        try:
            await self.local.pull(self.config.ollama_url, model, progress)
        except ProvisioningError as exc:
            raise JobError(str(exc)) from exc
        return {"model": model}
