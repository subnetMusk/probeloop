"""Server-side settings: the execution profile of the interviewer, analysis and evaluation."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from probeloop.ai.profiles import ProfiledChatModel
from probeloop.workspace.execution import (
    PROFILES,
    ExecutionProfiles,
    Profile,
    ProfileUnavailableError,
)
from probeloop.workspace.service import DataBusyError, DataService


class ExecutionModels(BaseModel):
    interviewer: str
    analysis: str
    evaluation: str


class ExecutionProfileView(BaseModel):
    id: Profile
    available: bool
    models: ExecutionModels | None  # model references per role; None when not configured


class ExecutionView(BaseModel):
    profile: Profile
    profiles: list[ExecutionProfileView]


class ExecutionChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Profile


async def _require_json(request: Request) -> None:
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=415, detail="content type must be application/json")


def settings_router(
    profiles: ExecutionProfiles, roles: Mapping[str, ProfiledChatModel], data: DataService
) -> APIRouter:
    router = APIRouter(prefix="/api/settings")
    refs = {role: model.model_refs() for role, model in roles.items()}

    def view() -> ExecutionView:
        return ExecutionView(
            profile=profiles.current,
            profiles=[
                ExecutionProfileView(
                    id=profile,
                    available=profile in profiles.available,
                    models=ExecutionModels(**{role: refs[role][profile] for role in refs})
                    if profile in profiles.available
                    else None,
                )
                for profile in PROFILES
            ],
        )

    @router.get("/execution")
    async def execution() -> ExecutionView:
        return view()

    @router.put("/execution", dependencies=[Depends(_require_json)])
    async def select_execution(choice: ExecutionChoice) -> ExecutionView:
        if choice.profile == profiles.current:
            return view()
        try:
            # No live interview and no queued or running job, so that no piece of work mixes
            # the models of two profiles. The API holds the mutation lock during this request.
            await data.ensure_idle()
            await profiles.select(choice.profile)
        except ProfileUnavailableError as exc:
            raise HTTPException(409, str(exc)) from exc
        except DataBusyError as exc:
            raise HTTPException(409, str(exc)) from exc
        return view()

    return router
