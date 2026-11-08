"""Versioned rubric loading and validation shared by the report use cases."""

from __future__ import annotations

import hashlib
from importlib.resources import files

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z_]+$")
    label: str
    anchors: dict[int, str]

    @model_validator(mode="after")
    def anchored(self) -> Criterion:
        if set(self.anchors) != {1, 3, 5} or not all(self.anchors.values()):
            raise ValueError("each criterion needs anchors for 1, 3 and 5")
        return self


class Rubric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: int = Field(ge=1)
    criteria: tuple[Criterion, ...] = Field(min_length=4, max_length=7)
    minimum_assessed_share: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def unique(self) -> Rubric:
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError("criterion ids must be unique")
        return self

    @property
    def ref(self) -> str:
        return f"{self.id}.v{self.version}"

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def data(self, *, descending: bool = False) -> list[dict[str, object]]:
        """The criteria as prompt data; the anchor order is part of the bias mitigation."""
        order = (5, 3, 1) if descending else (1, 3, 5)
        return [
            {"id": c.id, "label": c.label, "anchors": {str(n): c.anchors[n] for n in order}}
            for c in self.criteria
        ]

    def prompt(self, *, descending: bool = False) -> str:
        order = (5, 3, 1) if descending else (1, 3, 5)
        return "\n".join(
            f"{c.id} ({c.label}):\n" + "\n".join(f"  {n}: {c.anchors[n]}" for n in order)
            for c in self.criteria
        )


def load_rubric(name: str) -> Rubric:
    raw = files("probeloop.assessment").joinpath("rubrics", f"{name}.v1.yaml").read_text()
    return Rubric.model_validate(yaml.safe_load(raw))
