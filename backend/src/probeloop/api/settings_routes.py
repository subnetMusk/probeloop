"""Server-side settings: the execution profile and the ChatGPT sign-in of the cloud profile."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, model_validator

from probeloop.ai.chatgpt_auth import CALLBACK_PATH, ChatGptAccount, SignInError
from probeloop.ai.profiles import ProfiledChatModel
from probeloop.interview.infrastructure.jev_limits import (
    KEY_REJECTED,
    MAX_KEY_CHARS,
    UNREACHABLE,
    JevStatedLimitReader,
)
from probeloop.workspace.execution import (
    PROFILES,
    ExecutionProfiles,
    Profile,
    ProfileUnavailableError,
    Tool,
    ToolOption,
    execution_tools,
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


class JevView(BaseModel):
    configured: bool  # an API key is stored; the key itself is never returned


class ReconstructionView(BaseModel):
    enabled: bool  # the saved preference
    applies: bool  # it takes effect: the interviewer of new interviews is ChatGPT


class ExecutionView(BaseModel):
    profile: str
    profiles: list[ExecutionProfileView]
    chatgpt: ChatGptView
    jev: JevView
    tools: list[ToolRoleView]
    answer_reconstruction: ReconstructionView
    locked: bool


class JevKeyIn(BaseModel):
    # Checked in the route: a schema violation reply would echo the submitted key.
    model_config = ConfigDict(extra="forbid")
    key: str


def plain_key(value: str) -> str:
    value = value.strip()
    if (
        not value
        or len(value) > MAX_KEY_CHARS
        or any(c.isspace() or not c.isprintable() for c in value)
    ):
        raise HTTPException(422, "paste the Jev API key without spaces")
    return value


class ToolOptionView(BaseModel):
    id: Tool
    available: bool
    model_ref: str
    reason: str


class ToolRoleView(BaseModel):
    id: Literal["interviewer", "analysis", "evaluation", "limits"]
    selected: Tool
    options: list[ToolOptionView]


class ExecutionChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Profile | None = None
    tools: dict[Literal["interviewer", "analysis", "evaluation", "limits"], Tool] | None = None
    answer_reconstruction: bool | None = None

    @model_validator(mode="after")
    def one_choice(self) -> ExecutionChoice:
        if self.profile is not None and self.tools is not None:
            raise ValueError("choose a profile or tool selections")
        if self.tools == {} or (
            self.profile is None and self.tools is None and self.answer_reconstruction is None
        ):
            raise ValueError("choose a profile, tool selections or answer reconstruction")
        return self


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
    tool_options: Callable[[], Awaitable[Mapping[str, tuple[ToolOption, ...]]]],
    jev: JevStatedLimitReader,
) -> APIRouter:
    router = APIRouter()
    refs = {role: model.model_refs() for role, model in roles.items()}
    # The page to return to after each pending sign-in, by OAuth state.
    returns: dict[str, str] = {}

    async def view() -> ExecutionView:
        status = account.status()
        options = await tool_options()
        selected = execution_tools(profiles.current)
        try:
            await data.ensure_idle()
            locked = False
        except DataBusyError:
            locked = True
        return ExecutionView(
            locked=locked,
            profile=profiles.current,
            profiles=[
                ExecutionProfileView(
                    id=profile,
                    models=ExecutionModels(
                        **{
                            role: refs[role][profile]
                            for role in ("interviewer", "analysis", "evaluation")
                        }
                    ),
                )
                for profile in PROFILES
            ],
            chatgpt=ChatGptView(
                signed_in=status.signed_in, email=status.email, plan_usage=status.plan_usage
            ),
            jev=JevView(configured=jev.key.configured),
            answer_reconstruction=ReconstructionView(
                enabled=profiles.answer_reconstruction,
                applies=profiles.answer_reconstruction and selected["interviewer"] == "cloud",
            ),
            tools=[
                ToolRoleView(
                    id=role,
                    selected=selected[role],
                    options=[ToolOptionView(**asdict(option)) for option in choices],
                )
                for role, choices in options.items()
            ],
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
        return await view()

    @router.put("/api/settings/execution", dependencies=[Depends(_require_json)])
    async def select_execution(choice: ExecutionChoice) -> ExecutionView:
        await ensure_idle()
        tools = execution_tools(profiles.current)
        changes = execution_tools(choice.profile) if choice.profile else choice.tools or {}
        options = await tool_options()
        for role, tool in changes.items():
            if tool == tools[role]:
                continue
            option = next((o for o in options[role] if o.id == tool), None)
            if option is None:
                raise HTTPException(422, "unsupported tool for this role")
            if not option.available:
                detail = (
                    "sign in with ChatGPT first"
                    if tool == "cloud"
                    else f"{tool} is unavailable for {role}: {option.reason}"
                )
                raise HTTPException(409, detail)
        for role, tool in changes.items():
            tools[role] = tool
        # The default applies to new work only: preparations and interviews keep their own
        # profile (ADR 0015), so changing it needs no idle guard.
        try:
            if changes:
                await profiles.select_tools(tools)
            if choice.answer_reconstruction is not None:
                # Read when an interview's interviewer is built: a running one keeps its setting.
                await profiles.set_answer_reconstruction(choice.answer_reconstruction)
        except ProfileUnavailableError as exc:
            raise HTTPException(409, str(exc)) from exc
        return await view()

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
        await ensure_idle()
        tools = execution_tools(profiles.current)
        if "cloud" in tools.values():
            await profiles.select_tools(
                {role: "local" if tool == "cloud" else tool for role, tool in tools.items()}
            )
        await account.sign_out()
        return await view()

    @router.put("/api/settings/jev/key", dependencies=[Depends(_require_json)])
    async def save_jev_key(body: JevKeyIn) -> ExecutionView:
        await ensure_idle()
        key = plain_key(body.key)
        # The key is accepted only after the service confirms it; it never appears in a reply.
        outcome = await jev.verify(key)
        if outcome == "key_rejected":
            raise HTTPException(422, KEY_REJECTED)
        if outcome == "unreachable":
            raise HTTPException(503, UNREACHABLE)
        jev.key.save(key)
        logger.info("Jev API key saved")
        return await view()

    @router.post("/api/settings/jev/remove", dependencies=[Depends(_require_json)])
    async def remove_jev_key() -> ExecutionView:
        await ensure_idle()
        tools = execution_tools(profiles.current)
        if tools["limits"] == "jev":
            # The interviewer's own LLM reads the limits again, as it does without Jev.
            await profiles.select_tools({**tools, "limits": tools["interviewer"]})
        jev.key.clear()
        logger.info("Jev API key removed")
        return await view()

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
