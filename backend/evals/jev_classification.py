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
from probeloop.context.domain.model import Obligation

FIXTURES = Path(__file__).parent / "fixtures/synthetic/cv_check"
SWEEP = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
MIXED = "mixed"


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


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
    """One item per offer line holding labelled requirements, with its section heading."""
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
        quote = _norm(requirement["quote"])
        index = next((i for i, line in enumerate(lines) if quote in _norm(line)), None)
        if index is None:
            raise ValueError(f"requirement {requirement['id']} is not found in its offer")
        entry = by_line.setdefault(index, (OfferLine(lines[index], headings[index]), set()))
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
    quantities = [_norm(q["text"]) for q in labels.get("quantities", [])]
    headings = {_norm(s["text"]) for s in labels.get("sections", [])}
    return [
        CvItem(cv, line, any(q in _norm(line) for q in quantities), _norm(line) in headings)
        for line in _lines(text)
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


async def evaluate(
    classifier: TextClassifier, fixtures: Path, labels: dict[str, Any]
) -> dict[str, Any]:
    obligations: list[ObligationItem] = []
    for offer, data in sorted(labels["offers"].items()):
        text = (fixtures / "offers" / f"{offer}.txt").read_text()
        obligations += offer_items(offer, text, data["requirements"])
    cv_lines: list[CvItem] = []
    for cv, data in sorted(labels["cvs"].items()):
        cv_lines += cv_items(cv, (fixtures / "cvs" / f"{cv}.txt").read_text(), data)

    read = await classifier.obligations([item.line for item in obligations])
    quantified = await classifier.quantified([item.line for item in cv_lines])
    headings = await classifier.headings([item.line for item in cv_lines])

    gold_quantified = [item.quantified for item in cv_lines]
    gold_headings = [item.heading for item in cv_lines]
    return {
        "labels_version": labels.get("version"),
        "labels_status": labels.get("status"),
        "model_refs": {
            "obligation": read.model_ref,
            "quantified": quantified.model_ref,
            "heading": headings.model_ref,
        },
        "obligation": obligation_report(
            [item.gold for item in obligations], [r.obligation.value for r in read.readings]
        ),
        "quantified": {
            "at_threshold": precision_recall(
                gold_quantified, [r.positive for r in quantified.readings]
            ),
            "sweep": sweep(gold_quantified, [r.score for r in quantified.readings]),
        },
        "heading": {
            "at_threshold": precision_recall(
                gold_headings, [r.positive for r in headings.readings]
            ),
            "sweep": sweep(gold_headings, [r.score for r in headings.readings]),
        },
        "items": {
            "obligation": [
                {
                    "offer": i.offer,
                    "line": i.line.text,
                    "gold": i.gold,
                    "must": r.must,
                    "preferred": r.preferred,
                }
                for i, r in zip(obligations, read.readings, strict=True)
            ],
            "cv": [
                {
                    "cv": i.cv,
                    "line": i.line,
                    "quantified": i.quantified,
                    "heading": i.heading,
                    "quantified_score": q.score,
                    "heading_score": h.score,
                }
                for i, q, h in zip(cv_lines, quantified.readings, headings.readings, strict=True)
            ],
        },
    }


async def run(output: Path, *, allow_draft: bool) -> None:
    from probeloop.context.infrastructure.jev_classifier import JevTextClassifier
    from probeloop.platform.jev import JevKeyFile
    from probeloop.settings import Settings

    labels = load(FIXTURES, allow_draft=allow_draft)
    classifier = JevTextClassifier(JevKeyFile(Settings().data_dir / "typesafe"))
    try:
        result = await evaluate(classifier, FIXTURES, labels)
    finally:
        await classifier.aclose()
    output.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(output.write_text, json.dumps(result, ensure_ascii=False, indent=2))
    summary = {key: result[key] for key in ("model_refs", "obligation", "quantified", "heading")}
    summary["obligation"] = {k: v for k, v in result["obligation"].items() if k != "confusion"}
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-draft", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(run(arguments.output, allow_draft=arguments.allow_draft))
