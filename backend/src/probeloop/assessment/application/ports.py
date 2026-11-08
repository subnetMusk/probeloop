"""Persistence of versioned reports."""

from __future__ import annotations

from typing import Protocol

from probeloop.assessment.domain.model import Report, ReportKind


class ReportStore(Protocol):
    async def all(self) -> list[Report]: ...
    async def reports(self, kind: ReportKind, subject_id: str) -> list[Report]: ...

    async def get(self, report_id: str) -> Report | None: ...

    async def save(self, report: Report) -> None: ...
