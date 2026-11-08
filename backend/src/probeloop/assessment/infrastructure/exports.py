"""Local report exports; trusted templates escape data and all resource fetching is refused."""

from __future__ import annotations

import json
from typing import NoReturn

from jinja2 import Environment, PackageLoader
from weasyprint import HTML
from weasyprint.urls import FatalURLFetchingError, URLFetcher

from probeloop.assessment.application.labels import label
from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.domain.model import Report


class BlockedFetcher(URLFetcher):  # type: ignore[misc]  # Untyped dependency, isolated in this adapter.
    def fetch(self, url: str, headers: dict[str, str] | None = None) -> NoReturn:
        raise FatalURLFetchingError("report resource fetching is disabled")


def report_html(report: Report) -> str:
    environment = Environment(
        loader=PackageLoader("probeloop.assessment", "templates"),
        autoescape=True,
    )
    evidence_by_unit = {
        u.id: tuple(
            dict.fromkeys(e for s in report.unit_scores if s.unit_id == u.id for e in s.evidence)
        )
        for u in report.units
    }
    delivery_rows = {
        seq: {metric.id: metric.value for metric in report.delivery if metric.turn_seq == seq}
        for seq in dict.fromkeys(m.turn_seq for m in report.delivery if m.turn_seq is not None)
    }
    return environment.get_template("report.html.j2").render(
        report=report,
        it=report.language == "it",
        evidence_by_unit=evidence_by_unit,
        delivery_rows=delivery_rows,
        label=lambda value: label(value, report.language),
    )


def markdown(report: Report) -> str:
    def text(value: object) -> str:
        value = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for char in ("\\", "`", "*", "_", "[", "]", "#"):
            value = value.replace(char, "\\" + char)
        return value

    it = report.language == "it"
    title = (
        "Revisione CV"
        if report.kind.value == "cv" and it
        else "CV review"
        if report.kind.value == "cv"
        else "Report del colloquio"
        if it
        else "Interview report"
    )
    lines = [
        f"# {title}",
        "",
        text(report.disclaimer),
        "",
        f"{report.overall if report.overall is not None else 'NA'} / 5; "
        f"{report.assessed}/{report.criteria}",
        f"{report.rubric_id}; v{report.version}; {report.model_ref}",
        "",
    ]
    for score in (*report.scores, *report.unit_scores):
        lines.extend(
            [
                f"## {text(score.label)} ({text(score.unit_id or score.criterion_id)})",
                "",
                f"{score.value if score.value is not None else 'NA'} / 5"
                + (" - unstable" if score.unstable else ""),
                "",
                text(score.reason),
                "",
            ]
        )
        for evidence in score.evidence:
            lines.extend(
                [
                    f"> {text(evidence.quote).replace(chr(10), chr(10) + '> ')}",
                    f"Source: {text(evidence.source_id)}",
                    "",
                ]
            )
    for note in report.observations:
        lines.extend([f"## {text(label(note.kind, report.language))}", "", text(note.text), ""])
        for evidence in note.evidence:
            lines.extend(
                [
                    f"> {text(evidence.quote).replace(chr(10), chr(10) + '> ')}",
                    f"Source: {text(evidence.source_id)}",
                    "",
                ]
            )
        if note.replacement:
            lines.extend([text(note.replacement), ""])
    for check in report.checks:
        lines.extend([f"- {text(check.id)}: {text(check.status)} - {text(check.detail)}"])
        for evidence in check.evidence:
            lines.append(f"  > {text(evidence.quote).replace(chr(10), chr(10) + '  > ')}")
    lines.extend(["", "## Delivery", ""])
    for metric in report.delivery:
        lines.append(
            f"- {text(metric.id)} (turn {metric.turn_seq}): "
            f"{metric.value if metric.value is not None else 'NA'} "
            f"{text(metric.unit)} - {text(metric.detail)}"
        )
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            f"Input: {report.input_fingerprint}",
            f"Rubric: {report.rubric_hash}",
            f"Prompt: {text(report.prompt_ref)}",
            f"Snapshot: {text(report.snapshot_id)}",
            f"Revisions: {', '.join(f'{r.seq}:v{r.revision}' for r in report.revisions)}",
            f"Seconds: {report.duration_s}; dropped: {report.dropped}",
            "",
        ]
    )
    return "\n".join(lines)


def export_report(report: Report, format: str) -> bytes:
    if format == "json":
        return json.dumps(
            ReportData.of(report).model_dump(mode="json"), ensure_ascii=False, indent=2
        ).encode()
    if format == "md":
        return markdown(report).encode()
    if format == "pdf":
        result = HTML(string=report_html(report), url_fetcher=BlockedFetcher()).write_pdf()
        assert isinstance(result, bytes)
        return result
    raise ValueError("unknown report format")
