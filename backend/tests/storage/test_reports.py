from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.assessment.application.rubrics import load_rubric
from probeloop.assessment.domain.model import Evidence, Report, ReportKind, Score
from probeloop.context.application.snapshots import snapshot_of
from probeloop.storage.database import sessionmaker
from probeloop.storage.sql_context import SqlContextStore
from probeloop.storage.sql_reports import SqlReportStore
from tests.context.test_preparation import in_review


async def test_report_versions_survive_reopening_and_cannot_be_overwritten(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    context = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    preparation = in_review()
    for document in preparation.documents:
        await context.add_document(document)
    await context.save_preparation(preparation)
    snapshot = snapshot_of(preparation, "s1", 0)
    await context.save_snapshot(snapshot)
    rubric = load_rubric("cv")
    report = Report(
        id="r1",
        kind=ReportKind.CV,
        subject_id=snapshot.id,
        version=1,
        created_at=1,
        language="en",
        rubric_id=rubric.ref,
        rubric_hash=rubric.digest,
        model_ref="fake",
        prompt_ref="review_cv@v1",
        input_fingerprint="input",
        snapshot_id=snapshot.id,
        session_id=None,
        scores=(
            Score(
                "impact",
                "Impact",
                3,
                "Specific outcome.",
                (Evidence(preparation.documents[0].id, "riducendo i km percorsi del 12%"),),
            ),
        ),
        observations=(),
        checks=(),
        overall=None,
        assessed=1,
        criteria=7,
        dropped=0,
        duration_s=1,
        disclaimer="Formative review.",
    )
    store = SqlReportStore(sessionmaker(engine))
    await store.save(report)
    second = replace(report, id="r2", version=2, created_at=2)
    await store.save(second)
    reopened = SqlReportStore(sessionmaker(engine))
    assert await reopened.reports(ReportKind.CV, snapshot.id) == [report, second]
    assert await reopened.get(report.id) == report
    with pytest.raises(IntegrityError):
        await store.save(replace(report, id="duplicate"))
    assert await reopened.get(report.id) == report
