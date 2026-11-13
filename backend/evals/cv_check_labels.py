"""Check the CV check reference labels against GUIDE.md and the documents they describe.

Every quote must be found in its document, every value must be one the guide allows, every pair
must label every requirement of its offer, and an invariance variant must keep its base pair's
judgements. The labels are data for the evaluation; this check never changes them.

    python -m evals.cv_check_labels
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures/synthetic/cv_check"

CATEGORIES = {
    "skill",
    "knowledge",
    "experience",
    "education",
    "credential",
    "language",
    "eligibility",
    "interpersonal",
    "other",
}
OBLIGATIONS = {"must", "preferred", "unclear"}
THRESHOLDS = {"years", "language_level", "degree"}
ROUTES = {"education", "experience", "credential"}
COVERAGE = {"direct", "declared_only", "partial", "insufficient", "contradicted"}
RELATIONS = {"applied", "declared", "indirect", "contradicting"}
SPECIFICITY = {"outcome", "context", "mention"}
LEVELS = {"junior", "mid", "senior", "lead", None}
BANDS = {"strong", "partial", "weak", "insufficient_evidence"}
SECTIONS = {
    "profile",
    "experience",
    "projects",
    "education",
    "skills",
    "languages",
    "certifications",
    "other",
}
PRECISION = {"year", "month"}
QUANTITIES = {"outcome", "scope"}
DEFECTS = {
    "impossible_date",
    "contradiction",
    "vague_wording",
    "repetition",
    "missing_contact",
    "spelling",
}
SEVERITY = {"minor", "major"}


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def found(quote: str, text: str) -> bool:
    """Whether `quote` is in `text`, ignoring case and whitespace, line breaks included."""
    return bool(quote.strip()) and _norm(quote) in _norm(text)


def _words(quote: str) -> int:
    return len(re.findall(r"\w+", quote))


def problems(fixtures: Path = FIXTURES) -> list[str]:
    out: list[str] = []
    labels: dict[str, Any] = json.loads((fixtures / "labels.json").read_text())
    pairs = json.loads((fixtures / "pairs.json").read_text())["pairs"]
    if labels.get("status") not in {"draft", "frozen"}:
        out.append("status must be draft or frozen")
    if not isinstance(labels.get("version"), int):
        out.append("version must be an integer")

    requirement_ids: dict[str, list[str]] = {}
    for offer, data in labels.get("offers", {}).items():
        path = fixtures / "offers" / f"{offer}.txt"
        if not path.exists():
            out.append(f"{offer}: no offer file")
            continue
        out += _offer_problems(offer, path.read_text(), data.get("requirements", []))
        requirement_ids[offer] = [r.get("id") for r in data.get("requirements", [])]

    cv_texts: dict[str, str] = {}
    for cv in {pair["cv"] for pair in pairs}:
        path = fixtures / "cvs" / f"{cv}.txt"
        if path.exists():
            cv_texts[cv] = path.read_text()
        else:
            out.append(f"{cv}: no CV file")
    for cv, data in labels.get("cvs", {}).items():
        if cv not in cv_texts:
            out.append(f"{cv}: labelled but not used by a pair")
            continue
        out += _cv_problems(cv, cv_texts[cv], data)
    for cv in cv_texts:
        if cv not in labels.get("cvs", {}):
            out.append(f"{cv}: CV without labels")

    by_id = {pair["id"]: pair for pair in pairs}
    pair_labels: dict[str, Any] = labels.get("pairs", {})
    for pair in pairs:
        data = pair_labels.get(pair["id"])
        if data is None:
            out.append(f"{pair['id']}: pair without labels")
            continue
        out += _pair_problems(
            pair["id"],
            cv_texts.get(pair["cv"], ""),
            requirement_ids.get(pair["offer"], []),
            data,
        )
        base = pair.get("variant_of")
        if base and base in pair_labels:
            out += _invariance_problems(pair["id"], data, pair_labels[base])
        elif base and base not in by_id:
            out.append(f"{pair['id']}: unknown base pair {base}")
    for entry in labels.get("review", []):
        if not {"path", "before", "after", "reason"} <= set(entry):
            out.append(f"review entry without path, before, after and reason: {entry}")
    return out


def _offer_problems(offer: str, text: str, requirements: list[dict[str, Any]]) -> list[str]:
    out = []
    ids = [r.get("id") for r in requirements]
    if len(set(ids)) != len(ids):
        out.append(f"{offer}: duplicate requirement ids")
    for r in requirements:
        rid = r.get("id")
        where = f"{offer}/{rid}"
        if not isinstance(rid, str) or not rid.startswith(f"{offer}.r"):
            out.append(f"{where}: id must be {offer}.r<n>")
        if r.get("category") not in CATEGORIES:
            out.append(f"{where}: unknown category {r.get('category')!r}")
        if r.get("obligation") not in OBLIGATIONS:
            out.append(f"{where}: unknown obligation {r.get('obligation')!r}")
        if r.get("implicit"):
            if r.get("obligation") != "unclear":
                out.append(f"{where}: an implicit requirement is unclear")
        elif not found(r.get("quote") or "", text):
            out.append(f"{where}: quote not found in the offer")
        elif not 3 <= _words(r["quote"]) <= 40:
            out.append(f"{where}: quote needs 3 to 40 words")
        if (r.get("obligation") == "unclear") != (r.get("cue") is None):
            out.append(f"{where}: a cue is given exactly when the obligation is not unclear")
        if r.get("refines") is not None and r["refines"] not in ids:
            out.append(f"{where}: refines an unknown requirement")
        for member in r.get("any_of") or []:
            if not isinstance(member, dict) or not member.get("value"):
                out.append(f"{where}: an alternative member needs a value")
        for route in r.get("equivalents") or []:
            if not isinstance(route, dict) or route.get("kind") not in ROUTES:
                out.append(f"{where}: an equivalent route needs a known kind")
        threshold = r.get("threshold")
        if threshold is not None and (
            not isinstance(threshold, dict) or threshold.get("kind") not in THRESHOLDS
        ):
            out.append(f"{where}: unknown threshold")
    return out


def _cv_problems(cv: str, text: str, data: dict[str, Any]) -> list[str]:
    out = []
    checks = (
        ("sections", "text", "type", SECTIONS),
        ("dates", "text", "precision", PRECISION),
        ("quantities", "text", "kind", QUANTITIES),
        ("defects", "quote", "kind", DEFECTS),
        ("artefacts", "quote", None, None),
    )
    for field, text_key, enum_key, allowed in checks:
        for item in data.get(field, []):
            if not found(item.get(text_key) or "", text):
                out.append(f"{cv}/{field}: {item.get(text_key)!r} not found in the CV")
            if enum_key and allowed is not None and item.get(enum_key) not in allowed:
                out.append(f"{cv}/{field}: unknown {enum_key} {item.get(enum_key)!r}")
    for defect in data.get("defects", []):
        if defect.get("severity") not in SEVERITY:
            out.append(f"{cv}/defects: unknown severity {defect.get('severity')!r}")
    return out


def _pair_problems(pair: str, cv_text: str, ids: list[str], data: dict[str, Any]) -> list[str]:
    out = []
    if data.get("target_level") not in LEVELS:
        out.append(f"{pair}: unknown target_level")
    if data.get("fit_band") not in BANDS:
        out.append(f"{pair}: unknown fit_band")
    labelled = data.get("requirements", {})
    if set(labelled) != set(ids):
        out.append(f"{pair}: requirements differ from the offer's")
    for rid, item in labelled.items():
        where = f"{pair}/{rid}"
        coverage = item.get("coverage")
        evidence = item.get("evidence") or []
        if coverage not in COVERAGE:
            out.append(f"{where}: unknown coverage {coverage!r}")
        if len(evidence) > 2:
            out.append(f"{where}: at most two quotes")
        if coverage == "insufficient" and evidence:
            out.append(f"{where}: insufficient coverage has no evidence")
        if coverage in COVERAGE - {"insufficient"} and not evidence:
            out.append(f"{where}: {coverage} needs evidence")
        if coverage == "contradicted" and not any(
            e.get("relation") == "contradicting" for e in evidence
        ):
            out.append(f"{where}: contradicted needs contradicting evidence")
        if coverage == "declared_only" and any(e.get("relation") == "applied" for e in evidence):
            out.append(f"{where}: declared_only cannot cite applied evidence")
        for e in evidence:
            if not found(e.get("quote") or "", cv_text):
                out.append(f"{where}: quote {e.get('quote')!r} not found in the CV")
            if e.get("relation") not in RELATIONS:
                out.append(f"{where}: unknown relation {e.get('relation')!r}")
            if e.get("specificity") not in SPECIFICITY:
                out.append(f"{where}: unknown specificity {e.get('specificity')!r}")
        if not item.get("note"):
            out.append(f"{where}: a note is required")
    return out


def _invariance_problems(pair: str, data: dict[str, Any], base: dict[str, Any]) -> list[str]:
    out = []
    if data.get("fit_band") != base.get("fit_band"):
        out.append(f"{pair}: fit_band differs from its base pair")
    for rid, item in data.get("requirements", {}).items():
        other = base.get("requirements", {}).get(rid, {})
        if item.get("coverage") != other.get("coverage"):
            out.append(f"{pair}/{rid}: coverage differs from its base pair")
        relations = [e.get("relation") for e in item.get("evidence") or []]
        if relations != [e.get("relation") for e in other.get("evidence") or []]:
            out.append(f"{pair}/{rid}: evidence relations differ from its base pair")
    return out


if __name__ == "__main__":
    found_problems = problems()
    for problem in found_problems:
        print(problem)
    print(f"{len(found_problems)} problems", file=sys.stderr)
    sys.exit(1 if found_problems else 0)
