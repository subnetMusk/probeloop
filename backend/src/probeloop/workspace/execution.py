"""The execution profile: where the interviewer, document analysis and evaluation models run.

"local" keeps every model call on this machine. "cloud" sends those calls, with the documents,
transcripts and answers they contain, to the configured cloud provider. Speech recognition and
synthesis are not part of the profile: they always run locally.

The selection is a small JSON file in the data directory. It is configuration, not user data,
so backups, restores and "delete all my data" leave it alone.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Collection
from pathlib import Path
from typing import Literal, cast

logger = logging.getLogger(__name__)

type Profile = Literal["local", "cloud"]
PROFILES: tuple[Profile, ...] = ("local", "cloud")
DEFAULT: Profile = "local"


class ProfileUnavailableError(ValueError):
    pass


class ExecutionProfiles:
    def __init__(self, path: Path, available: Collection[Profile]) -> None:
        self._path = path
        self.available: tuple[Profile, ...] = tuple(p for p in PROFILES if p in available)
        self._selected = self._read()

    @property
    def current(self) -> Profile:
        """The selected profile, or the local one when the selection is no longer available."""
        return self._selected if self._selected in self.available else DEFAULT

    async def select(self, profile: Profile) -> None:
        """Persist `profile`. Callers make sure that no model work is in progress."""
        if profile not in self.available:
            raise ProfileUnavailableError(f"the {profile} profile is not configured")
        await asyncio.to_thread(self._write, profile)
        self._selected = profile

    def _read(self) -> Profile:
        try:
            value = json.loads(self._path.read_text(encoding="utf-8")).get("profile")
        except FileNotFoundError:
            return DEFAULT
        except (OSError, ValueError, AttributeError):
            logger.warning("unreadable execution profile; using the local profile")
            return DEFAULT
        return cast(Profile, value) if value in PROFILES else DEFAULT

    def _write(self, profile: Profile) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"profile": profile}), encoding="utf-8")
        temporary.replace(self._path)
