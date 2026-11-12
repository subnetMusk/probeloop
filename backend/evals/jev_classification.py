"""Measure a line classifier on the CV check reference labels; no language model is called.

The labels in `fixtures/synthetic/cv_check/` follow its GUIDE.md. Offer lines that hold labelled
requirements are classified for obligation, each with the heading of its section; every CV line
is classified as a quantified outcome or not, and as a section heading or not. The report gives
per-class precision and recall at the classifier's thresholds and over a sweep of thresholds,
which is the evidence needed before the classifier may be offered. Raw scores go to --output,
outside git.

    python -m evals.jev_classification --output /out/jev-classification.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from probeloop.context.application.ports import OfferLine, TextClassifier
from probeloop.context.domain.lines import logical_lines
from probeloop.context.domain.model import Obligation

FIXTURES = Path(__file__).parent / "fixtures/synthetic/cv_check"
SWEEP = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
MIXED = "mixed"


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _span(lines: Sequence[str], quote: str) -> tuple[int, int] | None:
    """The first and last line that `quote` covers, matching across line breaks."""
    starts, parts, position = [], [], 0
    for line in lines:
        part = _norm(line)
        starts.append(position)
        parts.append(part)
        position += len(part) + 1
    needle = _norm(quote)
    at = " ".join(parts).find(needle) if needle else -1
    if at < 0:
        return None
    end = at + len(needle) - 1
    first = max(i for i, start in enumerate(starts) if start <= at)
    return first, max(i for i, start in enumerate(starts) if start <= end)


def _is_offer_heading(line: str) -> bool:
    """A short line that is not a list item and does not end a sentence."""
    return not _BULLET.match(line) and len(line.split()) <= 6 and not line.endswith((".", ";"))


@dataclass(frozen=True, slots=True)
class ObligationItem:
    offer: str
    line: OfferLine
    gold: str  # an Obligation value, or MIXED when one line holds several obligations


def offer_items(
    offer: str, text: str, requirements: Sequence[dict[str, Any]]
) -> list[ObligationItem]:
    """One item per offer line holding labelled requirements, with its section heading. A
    requirement quoted across a line break is read with every line its quote covers."""
    heading: str | None = None
    by_line: dict[int, tuple[OfferLine, set[str]]] = {}
    lines = _lines(text)
    headings: list[str | None] = []
    for line in lines:
        if _is_offer_heading(line):
            heading = line.rstrip(":")
        headings.append(heading)
    for requirement in requirements:
        if requirement.get("implicit"):
            continue
        span = _span(lines, requirement["quote"])
        if span is None:
            raise ValueError(f"requirement {requirement['id']} is not found in its offer")
        first, last = span
        text = " ".join(lines[first : last + 1])
        entry = by_line.setdefault(first, (OfferLine(text, headings[first]), set()))
        entry[1].add(requirement["obligation"])
    return [
        ObligationItem(offer, line, next(iter(gold)) if len(gold) == 1 else MIXED)
        for _, (line, gold) in sorted(by_line.items())
    ]


@dataclass(frozen=True, slots=True)
class CvItem:
    cv: str
    line: str
    quantified: bool
    heading: bool


def cv_items(cv: str, text: str, labels: dict[str, Any]) -> list[CvItem]:
    """Every logical CV line, wrapped lines joined; a quantity marks the line where it starts."""
    lines = logical_lines(text)
    spans = [_span(lines, q["text"]) for q in labels.get("quantities", [])]
    quantified = {span[0] for span in spans if span is not None}
    headings = {_norm(s["text"]) for s in labels.get("sections", [])}
    return [
        CvItem(cv, line, i in quantified, _norm(line) in headings) for i, line in enumerate(lines)
    ]


def precision_recall(gold: Sequence[bool], predicted: Sequence[bool]) -> dict[str, float | int]:
    tp = sum(g and p for g, p in zip(gold, predicted, strict=True))
    fp = sum(p and not g for g, p in zip(gold, predicted, strict=True))
    fn = sum(g and not p for g, p in zip(gold, predicted, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "support": tp + fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(2 * precision * recall / (precision + recall), 3) if tp else 0.0,
    }


def obligation_report(gold: Sequence[str], predicted: Sequence[str]) -> dict[str, Any]:
    classes = [o.value for o in Obligation]
    confusion = {g: {p: 0 for p in classes} for g in [*classes, MIXED]}
    for g, p in zip(gold, predicted, strict=True):
        confusion[g][p] += 1
    scored = [(g, p) for g, p in zip(gold, predicted, strict=True) if g != MIXED]
    return {
        "per_class": {
            c: precision_recall([g == c for g, _ in scored], [p == c for _, p in scored])
            for c in classes
        },
        "mixed_left_unclear": confusion[MIXED][Obligation.UNCLEAR.value],
        "mixed": sum(confusion[MIXED].values()),
        "confusion": confusion,
    }


def sweep(gold: Sequence[bool], scores: Sequence[float]) -> dict[str, Any]:
    return {str(t): precision_recall(gold, [s >= t for s in scores]) for t in SWEEP}


def load(fixtures: Path, *, allow_draft: bool) -> dict[str, Any]:
    labels: dict[str, Any] = json.loads((fixtures / "labels.json").read_text())
    if labels.get("status") != "frozen" and not allow_draft:
        raise SystemExit("the reference labels are not frozen; pass --allow-draft to try them")
    return labels


TASKS = ("obligation", "quantified", "heading")
# Wordings and batch sizes are compared on these CVs; the others are kept for one final measure.
# A variant stays with its base CV.
DEV_CVS = frozenset(
    {
        "c01-galli",
        "c01-galli--headings",
        "c01-galli--order",
        "c03-frontend-junior",
        "c05-supporto-it",
        "c07-contabile",
        "c07-contabile--name",
        "c09-accademico",
    }
)


def in_split(cv: str, split: str) -> bool:
    return split == "all" or (cv in DEV_CVS) == (split == "dev")


async def evaluate(
    classifier: TextClassifier,
    fixtures: Path,
    labels: dict[str, Any],
    *,
    split: str = "all",
    tasks: Sequence[str] = TASKS,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "labels_version": labels.get("version"),
        "labels_status": labels.get("status"),
        "split": split,
        "model_refs": {},
        "items": {},
    }
    if "obligation" in tasks:
        obligations: list[ObligationItem] = []
        for offer, data in sorted(labels["offers"].items()):
            text = (fixtures / "offers" / f"{offer}.txt").read_text()
            obligations += offer_items(offer, text, data["requirements"])
        read = await classifier.obligations([item.line for item in obligations])
        result["model_refs"]["obligation"] = read.model_ref
        result["obligation"] = obligation_report(
            [item.gold for item in obligations], [r.obligation.value for r in read.readings]
        )
        result["items"]["obligation"] = [
            {
                "offer": i.offer,
                "line": i.line.text,
                "gold": i.gold,
                "must": r.must,
                "preferred": r.preferred,
            }
            for i, r in zip(obligations, read.readings, strict=True)
        ]
    cv_lines: list[CvItem] = []
    for cv, data in sorted(labels["cvs"].items()):
        if in_split(cv, split):
            cv_lines += cv_items(cv, (fixtures / "cvs" / f"{cv}.txt").read_text(), data)
    for task in ("quantified", "heading"):
        if task not in tasks:
            continue
        lines = [item.line for item in cv_lines]
        readings = await (
            classifier.quantified(lines) if task == "quantified" else classifier.headings(lines)
        )
        gold = [item.quantified if task == "quantified" else item.heading for item in cv_lines]
        result["model_refs"][task] = readings.model_ref
        result[task] = {
            "at_threshold": precision_recall(gold, [r.positive for r in readings.readings]),
            "sweep": sweep(gold, [r.score for r in readings.readings]),
        }
        result["items"][task] = [
            {"cv": i.cv, "line": i.line, "gold": g, "score": r.score}
            for i, g, r in zip(cv_lines, gold, readings.readings, strict=True)
        ]
    return result


async def run(
    output: Path,
    *,
    allow_draft: bool,
    max_questions: int | None,
    split: str,
    tasks: Sequence[str],
    wordings: str,
) -> None:
    from probeloop.context.infrastructure import jev_classifier
    from probeloop.platform.jev import JevKeyFile
    from probeloop.settings import Settings

    labels = load(FIXTURES, allow_draft=allow_draft)
    line_wordings = (
        {"quantified": jev_classifier.QUANTIFIED, "heading": jev_classifier.HEADING}
        if wordings == "v1"
        else jev_classifier.LINE_WORDINGS
    )
    classifier = jev_classifier.JevTextClassifier(
        JevKeyFile(Settings().data_dir / "typesafe"),
        max_questions=max_questions or jev_classifier.MAX_QUESTIONS,
        line_wordings=line_wordings,
    )
    try:
        result = await evaluate(classifier, FIXTURES, labels, split=split, tasks=tasks)
    finally:
        await classifier.aclose()
    output.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(output.write_text, json.dumps(result, ensure_ascii=False, indent=2))
    summary = {key: result[key] for key in ("model_refs", *TASKS) if key in result}
    if "obligation" in summary:
        summary["obligation"] = {k: v for k, v in result["obligation"].items() if k != "confusion"}
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument(
        "--max-questions", type=int, help="questions per request, to compare batch sizes"
    )
    parser.add_argument("--split", choices=("all", "dev", "test"), default="all")
    parser.add_argument("--tasks", default=",".join(TASKS), help="comma-separated tasks")
    parser.add_argument("--wordings", choices=("v1", "v2"), default="v2")
    arguments = parser.parse_args()
    asyncio.run(
        run(
            arguments.output,
            allow_draft=arguments.allow_draft,
            max_questions=arguments.max_questions,
            split=arguments.split,
            tasks=arguments.tasks.split(","),
            wordings=arguments.wordings,
        )
    )
