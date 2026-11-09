"""Local report exports; trusted templates escape data and refuse resource fetching."""

from __future__ import annotations

import json
from typing import NoReturn

from jinja2 import Environment, PackageLoader
from weasyprint import HTML
from weasyprint.urls import FatalURLFetchingError, URLFetcher

from probeloop.assessment.application.labels import label, section_label
from probeloop.assessment.application.outline import (
    Criterion,
    ExportSources,
    Note,
    Quote,
    report_outline,
)
from probeloop.assessment.application.schemas import ReportData
from probeloop.assessment.domain.model import Report


class BlockedFetcher(URLFetcher):  # type: ignore[misc]  # Untyped dependency, isolated in this adapter.
    def fetch(self, url: str, headers: dict[str, str] | None = None) -> NoReturn:
        raise FatalURLFetchingError("report resource fetching is disabled")


def report_html(report: Report, sources: ExportSources | None = None) -> str:
    sources = sources or ExportSources({})
    outline = report_outline(
        report, sources.transcript, requirements=sources.requirements, original=sources.original
    )
    environment = Environment(
        loader=PackageLoader("probeloop.assessment", "templates"), autoescape=True
    )
    return environment.get_template("report.html.j2").render(
        report=report,
        outline=outline,
        label=lambda value: label(value, report.language),
        heading=lambda value: section_label(value, report.language),
    )


def markdown(report: Report, sources: ExportSources | None = None) -> str:
    sources = sources or ExportSources({})
    outline = report_outline(
        report, sources.transcript, requirements=sources.requirements, original=sources.original
    )

    def loc(value: str) -> str:
        return label(value, report.language)

    def text(value: object) -> str:
        value = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for char in ("\\", "`", "*", "_", "[", "]", "#", "|", "!"):
            value = value.replace(char, "\\" + char)
        return value

    def value(number: float | None) -> str:
        return str(number) if number is not None else loc("Not assessable")

    lines = [f"# {outline.title}", "", f"ProbeLoop · v{report.version}", ""]

    def quotes(items: tuple[Quote, ...]) -> None:
        for item in items:
            suffix = f" ({loc('Answer')} {item.answer})" if item.answer is not None else ""
            lines.extend([f"> {text(item.text).replace(chr(10), chr(10) + '> ')}{suffix}", ""])

    def notes(items: tuple[Note, ...]) -> None:
        if not items:
            lines.extend([loc("No evidence-backed observations."), ""])
        for item in items:
            if item.unit is not None:
                lines.extend([f"### {loc('Question')} {item.unit}", ""])
            lines.extend([text(item.text), ""])
            quotes(item.quotes)
            if item.replacement:
                lines.extend([f"**{loc('Suggested correction')}**", "", text(item.replacement), ""])

    def criteria(items: tuple[Criterion, ...]) -> None:
        for item in items:
            lines.extend(
                [
                    f"### {text(item.label)}: {value(item.value)} / 5"
                    + (" *" if item.unstable else ""),
                    "",
                    text(item.reason),
                    "",
                ]
            )
            quotes(item.quotes)

    for section in outline.sections:
        lines.extend([f"## {section_label(section, report.language)}", ""])
        if section == "overview":
            lines.extend(
                [
                    f"{value(outline.overall)} / 5 · {loc(outline.band) if outline.band else ''}",
                    f"{outline.assessed}/{outline.criteria_count}",
                    "",
                ]
            )
            if outline.summary:
                notes((outline.summary,))
        elif section in {"improvements", "strengths", "rewrites", "practice"}:
            notes(getattr(outline, section))
        elif section == "criteria":
            criteria(outline.criteria)
        elif section == "questions":
            for unit in outline.units:
                lines.extend([f"### {loc('Question')} {unit.number}", ""])
                lines.extend(f"{text(question)}\n" for question in unit.questions)
                for answer in unit.answers:
                    lines.extend(
                        [f"**{loc('Answer')} {answer.number}**", "", text(answer.text), ""]
                    )
                if unit.scored:
                    criteria(unit.scores)
                else:
                    lines.extend([f"{loc(unit.kind)} · {loc('Not scored')}", ""])
            lines.extend([f"### {loc('Assessment criteria')}", ""])
            criteria(outline.criteria)
        elif section == "requirements":
            for row in outline.requirements:
                lines.extend(
                    [
                        f"- {text(row.text)}",
                        f"  {loc('In the interview')}: "
                        f"{loc(row.interview) if row.interview else '—'}; "
                        f"{loc('In your documents')}: "
                        f"{loc(row.documents) if row.documents else '—'}",
                        "",
                    ]
                )
                quotes(row.quotes)
        elif section == "checks":
            for check in outline.checks:
                lines.extend([f"- {loc(check.status)}: {text(check.detail)}", ""])
                quotes(check.quotes)
        elif section == "delivery" and outline.delivery:
            delivery = outline.delivery
            for name, number, suffix in (
                ("Median pace", delivery.median_rate, loc("Words/min")),
                ("Median response latency", delivery.median_latency, "s"),
                ("Fillers per minute", delivery.fillers_per_minute, ""),
                ("Long pauses", delivery.long_pauses, ""),
                ("Talk share", delivery.talk_share, "%"),
                ("Answer budget used", delivery.budget_share, "%"),
            ):
                lines.append(
                    f"- {loc(name)}: {value(number)}" + (f" {suffix}" if number is not None else "")
                )
            lines.append("")
        elif section == "original":
            lines.extend(
                [text(outline.original or loc("Typed text: there is no original file.")), ""]
            )
        elif section == "technical":
            about = outline.technical
            for name, item in (
                ("Model", about.model),
                ("Prompt", about.prompt),
                ("Rubric", f"{about.rubric} · {about.rubric_hash}"),
                ("Input hash", about.fingerprint),
                ("Discarded model items", about.dropped),
                ("Edited answers assessed", about.edited_answers),
                ("Processing time", f"{about.duration_s} s"),
            ):
                lines.append(f"- {loc(name)}: {text(item)}")
            if outline.unstable:
                lines.extend(["", "* " + loc("Judgements differ by at least two points.")])
            lines.extend(["", text(about.disclaimer), ""])
    if outline.delivery:
        lines.extend([f"## {loc('Measures for each answer')}", ""])
        columns = ("Answer", "Duration (s)", "Words/min", "Fillers", "Long pauses", "Latency (s)")
        lines.extend([" | ".join(loc(c) for c in columns), " | ".join("---" for _ in columns)])
        for measurement in outline.delivery.per_answer:
            lines.append(
                " | ".join(
                    [
                        str(measurement.answer),
                        *(
                            value(v)
                            for v in (
                                measurement.duration,
                                measurement.rate,
                                measurement.fillers,
                                measurement.pauses,
                                measurement.latency,
                            )
                        ),
                    ]
                )
            )
    return "\n".join(lines) + "\n"


def export_report(report: Report, format: str, sources: ExportSources | None = None) -> bytes:
    if format == "json":
        return json.dumps(
            ReportData.of(report).model_dump(mode="json"), ensure_ascii=False, indent=2
        ).encode()
    if format == "md":
        return markdown(report, sources).encode()
    if format == "pdf":
        result = HTML(string=report_html(report, sources), url_fetcher=BlockedFetcher()).write_pdf()
        assert isinstance(result, bytes)
        return result
    raise ValueError("unknown report format")
