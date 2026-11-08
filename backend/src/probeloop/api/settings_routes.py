"""Server-side settings: the execution profile and the ChatGPT sign-in of the cloud profile."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict

from probeloop.ai.chatgpt_auth import CALLBACK_PATH, ChatGptAccount, SignInError
from probeloop.ai.profiles import ProfiledChatModel
from probeloop.workspace.execution import (
    PROFILES,
    ExecutionProfiles,
    Profile,
    ProfileUnavailableError,
)
from probeloop.workspace.service import DataBusyError, DataService

logger = logging.getLogger(__name__)


class ExecutionModels(BaseModel):
    interviewer: str
    analysis: str
    evaluation: str


class ExecutionProfileView(BaseModel):
    id: Profile
    models: ExecutionModels  # model references per role


class ChatGptView(BaseModel):
    signed_in: bool
    email: str | None
    plan_usage: bool  # the account allowed ProbeLoop to use its ChatGPT plan


class ExecutionView(BaseModel):
    profile: Profile
    profiles: list[ExecutionProfileView]
    chatgpt: ChatGptView


class ExecutionChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Profile


class SignInStart(BaseModel):
    url: str  # where the browser continues the sign-in


async def _require_json(request: Request) -> None:
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=415, detail="content type must be application/json")


def settings_router(
    profiles: ExecutionProfiles,
    roles: Mapping[str, ProfiledChatModel],
    data: DataService,
    account: ChatGptAccount,
    allowed_origins: Sequence[str],
) -> APIRouter:
    router = APIRouter()
    refs = {role: model.model_refs() for role, model in roles.items()}
    # The page to return to after each pending sign-in, by OAuth state.
    returns: dict[str, str] = {}

    def view() -> ExecutionView:
        status = account.status()
        return ExecutionView(
            profile=profiles.current,
            profiles=[
                ExecutionProfileView(
                    id=profile,
                    models=ExecutionModels(**{role: refs[role][profile] for role in refs}),
                )
                for profile in PROFILES
            ],
            chatgpt=ChatGptView(
                signed_in=status.signed_in, email=status.email, plan_usage=status.plan_usage
            ),
        )

    async def ensure_idle() -> None:
        try:
            # No live interview and no queued or running job, so that no piece of work mixes
            # the models of two profiles. The API holds the mutation lock during the request.
            await data.ensure_idle()
        except DataBusyError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/api/settings/execution")
    async def execution() -> ExecutionView:
        return view()

    @router.put("/api/settings/execution", dependencies=[Depends(_require_json)])
    async def select_execution(choice: ExecutionChoice) -> ExecutionView:
        if choice.profile == profiles.current:
            return view()
        if choice.profile == "cloud" and not account.status().plan_usage:
            raise HTTPException(409, "sign in with ChatGPT first")
        await ensure_idle()
        try:
            await profiles.select(choice.profile)
        except ProfileUnavailableError as exc:
            raise HTTPException(409, str(exc)) from exc
        return view()

    @router.post("/api/settings/chatgpt/sign-in", dependencies=[Depends(_require_json)])
    async def sign_in(request: Request) -> SignInStart:
        origin = request.headers.get("origin") or f"{request.url.scheme}://{request.url.netloc}"
        if origin not in allowed_origins:
            raise HTTPException(403, "origin not allowed")
        # OpenAI requires a loopback redirect on 127.0.0.1; only the port may vary.
        port = urlsplit(origin).port or (443 if origin.startswith("https") else 80)
        url = account.begin(f"http://127.0.0.1:{port}{CALLBACK_PATH}")
        state = parse_qs(urlsplit(url).query).get("state", [""])[0]
        returns[state] = origin
        return SignInStart(url=url)

    @router.post("/api/settings/chatgpt/sign-out", dependencies=[Depends(_require_json)])
    async def sign_out() -> ExecutionView:
        if profiles.current == "cloud":
            await ensure_idle()
            await profiles.select("local")
        await account.sign_out()
        return view()

    @router.get(CALLBACK_PATH, include_in_schema=False)
    async def callback(request: Request) -> RedirectResponse:
        query = dict(request.query_params)
        origin = returns.pop(query.get("state", ""), "")
        try:
            status = await account.complete(query)
            outcome = "connected" if status.plan_usage else "no-plan"
        except SignInError as exc:
            outcome = exc.reason
        logger.info("ChatGPT sign-in finished", extra={"outcome": outcome})
        target = origin if origin in allowed_origins else ""
        return RedirectResponse(f"{target}/settings?chatgpt={outcome}", status_code=303)

    return router
