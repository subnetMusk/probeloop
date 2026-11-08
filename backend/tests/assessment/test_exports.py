from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import pdfplumber
import pytest
from weasyprint import HTML
from weasyprint.urls import FatalURLFetchingError

from probeloop.assessment.domain.model import Observation, Report, ReportKind
from probeloop.assessment.infrastructure.exports import BlockedFetcher, export_report, report_html


def sample_report() -> Report:
    return Report(
        id="report",
        kind=ReportKind.INTERVIEW,
        subject_id="synthetic",
        version=1,
        created_at=0,
        language="en",
        rubric_id="interview.v1",
        rubric_hash="a" * 64,
        model_ref="fake",
        prompt_ref="judge_unit@v1",
        input_fingerprint="b" * 64,
        snapshot_id=None,
        session_id="synthetic",
        scores=(),
        observations=(),
        checks=(),
        overall=None,
        assessed=0,
        criteria=0,
        dropped=0,
        duration_s=1,
        disclaimer="A formative practice assessment.",
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/image",
        "file:///etc/passwd",
        "data:text/plain,secret",
        "ftp://example.test/file",
    ],
)
def test_every_resource_scheme_is_refused(url: str) -> None:
    with pytest.raises(FatalURLFetchingError, match="disabled"):
        BlockedFetcher().fetch(url)


def test_export_escapes_markup_and_pdf_has_searchable_report_text() -> None:
    report = replace(
        sample_report(),
        observations=(Observation("summary", '<img src="file:///etc/passwd">', ()),),
    )
    html = report_html(report)
    assert '<img src="file:///etc/passwd">' not in html
    assert "&lt;img" in html
    pdf = export_report(report, "pdf")
    assert pdf.startswith(b"%PDF")
    with pdfplumber.open(BytesIO(pdf)) as document:
        text = "\n".join(page.extract_text() or "" for page in document.pages)
    assert "A formative practice assessment." in text
    assert "file:///etc/passwd" in text


def test_renderer_does_not_fall_back_to_fetching_resources() -> None:
    with pytest.raises(FatalURLFetchingError, match="disabled"):
        HTML(
            string='<img src="https://example.test/image">', url_fetcher=BlockedFetcher()
        ).write_pdf()
