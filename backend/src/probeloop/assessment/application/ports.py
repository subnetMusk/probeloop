"""Persistence of versioned reports."""

from __future__ import annotations

from typing import Protocol

from probeloop.assessment.domain.model import Report, ReportKind


class ReportStore(Protocol):
    async def all(self) -> list[Report]: ...
    async def reports(self, kind: ReportKind, subject_id: str) -> list[Report]: ...

    async def get(self, report_id: str) -> Report | None: ...

    async def save(self, report: Report) -> None: ...

    async def adopt_cv_reports(self, snapshot_id: str, profile_id: str) -> int:
        """Give the CV reports of a context that have no owner to this profile."""
        ...

    async def delete_cv_check(self, snapshot_id: str) -> bool:
        """Delete every version of the CV review of a context, with its finished jobs."""
        ...
