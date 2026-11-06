"""Versioned prompt templates rendered with Jinja2.

Templates live in a package's `prompts/` directory and are named `<name>.v<version>.j2`. The
returned reference (`<name>@v<version>`) is stored with every artifact the prompt produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Any

from jinja2 import Environment, StrictUndefined


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    text: str
    ref: str


class PromptRenderer:
    def __init__(self, package: str) -> None:
        self._root = resources.files(package).joinpath("prompts")
        self._env = Environment(
            autoescape=False,  # noqa: S701 - plain-text prompts, never rendered as HTML
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )

    def render(self, name: str, version: int, **variables: Any) -> RenderedPrompt:
        source = self._root.joinpath(f"{name}.v{version}.j2").read_text(encoding="utf-8")
        text = self._env.from_string(source).render(**variables).strip()
        return RenderedPrompt(text=text, ref=f"{name}@v{version}")
