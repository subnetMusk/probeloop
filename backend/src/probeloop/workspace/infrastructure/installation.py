"""Atomic machine configuration, separate from portable user data and authentication tokens."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from probeloop.workspace.installation import InstallationConfig


class InstallationFile:
    def __init__(self, path: Path, default: InstallationConfig) -> None:
        self.path = path
        try:
            self._config = InstallationConfig(**json.loads(path.read_text("utf-8")))
        except FileNotFoundError:
            self.save(default)

    def read(self) -> InstallationConfig:
        return self._config

    def save(self, config: InstallationConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(config)), encoding="utf-8")
        temporary.replace(self.path)
        self._config = config
