"""Per-role tools and frozen execution plans, including legacy uniform execution profiles.

"local" keeps every model call on this machine. "cloud" sends those calls, with the documents,
transcripts and answers they contain, to the configured cloud provider. Speech recognition and
synthesis are not part of the profile: they always run locally.

The selection is a small JSON file in the data directory. It is configuration, not user data,
so backups, restores and "delete all my data" leave it alone. The same file keeps whether the
cloud interviewer also returns its reading of each spoken answer (answer reconstruction).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

logger = logging.getLogger(__name__)

type Profile = Literal["local", "cloud"]
PROFILES: tuple[Profile, ...] = ("local", "cloud")
DEFAULT: Profile = "local"
type Tool = Literal["local", "cloud", "laya", "jev"]
ROLES = ("interviewer", "analysis", "evaluation", "limits")
# The tools each role accepts. Only stated-limit reading has engines besides the LLMs: the local
# Laya classifier and the TypeSafe Jev service. Both remain optional.
ROLE_TOOLS: dict[str, tuple[Tool, ...]] = {
    "interviewer": ("local", "cloud"),
    "analysis": ("local", "cloud"),
    "evaluation": ("local", "cloud"),
    "limits": ("local", "cloud", "laya", "jev"),
}


@dataclass(frozen=True, slots=True)
class ToolOption:
    id: Tool
    available: bool
    model_ref: str
    reason: str = "ready"


def execution_tools(profile: str | None) -> dict[str, Tool]:
    """Decode a frozen execution plan, including profiles written before per-role settings."""
    if profile is None or profile in PROFILES:
        provider = profile or DEFAULT
        return dict.fromkeys(ROLES, provider)
    value = json.loads(profile)
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("unsupported execution plan")
    tools = value.get("tools")
    if not isinstance(tools, dict) or set(tools) != set(ROLES):
        raise ValueError("invalid execution tools")
    for role, tool in tools.items():
        if tool not in ROLE_TOOLS[role]:
            raise ValueError("unsupported tool for this role")
    return cast(dict[str, Tool], tools)


def execution_plan(tools: Mapping[str, Tool]) -> str:
    """Keep legacy uniform profiles readable; mixed plans are self-contained for backups."""
    encoded = json.dumps({"version": 1, "tools": dict(tools)}, sort_keys=True)
    execution_tools(encoded)
    if len(set(tools.values())) == 1 and tools["interviewer"] in PROFILES:
        return tools["interviewer"]
    return encoded


def tool_for(profile: str | None, role: str) -> Tool:
    return execution_tools(profile)[role]


class ProfileUnavailableError(ValueError):
    pass


class ExecutionProfiles:
    def __init__(
        self, path: Path, available: Collection[Profile], *, default: Profile = DEFAULT
    ) -> None:
        self._path = path
        self._default = default
        self.available: tuple[Profile, ...] = tuple(p for p in PROFILES if p in available)
        self._reconstruction = False
        self._selected = self._read()

    @property
    def current(self) -> str:
        """The selected profile, or the local one when the selection is no longer available."""
        if self._selected in PROFILES and self._selected not in self.available:
            return DEFAULT
        return self._selected

    async def select(self, profile: Profile) -> None:
        """Persist a uniform legacy profile. Callers ensure no model work is in progress."""
        if profile not in self.available:
            raise ProfileUnavailableError(f"the {profile} profile is not configured")
        await asyncio.to_thread(self._write, profile)
        self._selected = profile

    async def select_tools(self, tools: Mapping[str, Tool]) -> None:
        plan = execution_plan(tools)
        await asyncio.to_thread(self._write, plan)
        self._selected = plan

    @property
    def answer_reconstruction(self) -> bool:
        """Whether spoken answers get the interviewer's reading. Only a cloud interviewer
        writes one: the local models measured so far rewrote answers instead of correcting them."""
        return self._reconstruction

    async def set_answer_reconstruction(self, enabled: bool) -> None:
        previous = self._reconstruction
        self._reconstruction = enabled
        try:
            await asyncio.to_thread(self._write, self._selected)
        except OSError:
            self._reconstruction = previous
            raise

    def _read(self) -> str:
        try:
            stored = json.loads(self._path.read_text(encoding="utf-8"))
            value = stored.get("profile")
            self._reconstruction = stored.get("answer_reconstruction") is True
        except FileNotFoundError:
            # Persist the initial choice too: a restarted first-run installation must not
            # acquire a different default merely because its database now exists.
            self._write(self._default)
            return self._default
        except (OSError, ValueError, AttributeError):
            logger.warning("unreadable execution profile; using the local profile")
            return DEFAULT
        if not isinstance(value, str):
            return DEFAULT
        try:
            execution_tools(value)
        except (ValueError, TypeError):
            logger.warning("invalid execution plan; using the local profile")
            return DEFAULT
        return value

    def _write(self, profile: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        content = {"profile": profile, "answer_reconstruction": self._reconstruction}
        temporary.write_text(json.dumps(content), encoding="utf-8")
        temporary.replace(self._path)
