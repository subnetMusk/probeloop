"""The approved context, and the briefs the interviewer reads.

The snapshot holds the facts the user kept, with the user's corrections applied, the requirement
matches, the target area and the documents. Its hash covers the content only, so the same
approved content always gives the same hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from typing import Any

from probeloop.context.domain.model import (
    ContextSnapshot,
    Fact,
    FactKind,
    FactOrigin,
    JobMode,
    MatchStatus,
    Preparation,
    RequirementMatch,
    Review,
    Subject,
)

MAX_BRIEF_CHARS = 3500

_KIND_ORDER = [
    FactKind.ROLE,
    FactKind.PROJECT,
    FactKind.ACHIEVEMENT,
    FactKind.SKILL,
    FactKind.EDUCATION,
    FactKind.CERTIFICATION,
    FactKind.LANGUAGE,
    FactKind.OTHER,
    FactKind.COMPANY,
    FactKind.RESPONSIBILITY,
    FactKind.REQUIREMENT,
    FactKind.NICE_TO_HAVE,
]
_ORIGIN_LABELS = {
    FactOrigin.DECLARED: "stated in the documents",
    FactOrigin.INFERRED: "inferred, not literally stated",
    FactOrigin.USER: "added by the candidate",
}


def snapshot_of(preparation: Preparation, snapshot_id: str, now: float) -> ContextSnapshot:
    candidate = tuple(preparation.included_facts(Subject.CANDIDATE))
    job = tuple(preparation.included_facts(Subject.JOB))
    kept = {f.id for f in candidate}
    requirements = {f.id for f in job}
    matches = tuple(
        RequirementMatch(
            m.requirement_id, m.status, tuple(i for i in m.fact_ids if i in kept), m.rationale
        )
        for m in preparation.matches
        if m.requirement_id in requirements
    )
    facts_by_id = {f.id: _fact_key(f) for f in (*candidate, *job)}
    content: dict[str, Any] = {
        "language": preparation.language,
        "job_mode": preparation.job_mode.value,
        "candidate": [_fact_key(f) for f in candidate],
        "job": [_fact_key(f) for f in job],
        "matches": [
            [facts_by_id[m.requirement_id], m.status.value, [facts_by_id[i] for i in m.fact_ids]]
            for m in matches
        ],
        "area": [preparation.area.area, preparation.area.seniority] if preparation.area else None,
        "vocabulary": list(preparation.vocabulary),
        "documents": [
            [d.kind.value, d.origin.value, d.title, hashlib.sha256(d.text.encode()).hexdigest()]
            for d in preparation.documents
        ],
    }
    if preparation.role_profile is not None:
        content["role_profile"] = asdict(preparation.role_profile)
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return ContextSnapshot(
        id=snapshot_id,
        preparation_id=preparation.id,
        created_at=now,
        language=preparation.language,
        job_mode=preparation.job_mode,
        candidate_facts=candidate,
        job_facts=job,
        matches=matches,
        area=preparation.area,
        vocabulary=preparation.vocabulary,
        documents=tuple(preparation.documents),
        content_hash=digest,
        role_profile=preparation.role_profile,
    )


def _fact_key(fact: Fact) -> list[Any]:
    return [
        fact.kind.value,
        fact.text,
        fact.origin.value,
        fact.quote,
        fact.review is Review.CORRECTED,
    ]


def candidate_brief(snapshot: ContextSnapshot) -> str:
    if not snapshot.candidate_facts:
        return "No information about the candidate was provided."
    if snapshot.role_profile is not None:
        profile = snapshot.role_profile
        return selected_fact_brief(
            snapshot.candidate_facts,
            query=" ".join((profile.target_role, *profile.competencies)),
            preferred_ids=profile.basis_fact_ids,
        )
    return _limit(_facts_by_kind(snapshot.candidate_facts))


def job_brief(snapshot: ContextSnapshot) -> str:
    if snapshot.role_profile is not None:
        profile = snapshot.role_profile
        return (
            "Confirmed target expectations (not candidate abilities):\n"
            + json.dumps(asdict(profile), ensure_ascii=False)
            + "\n"
            + selected_fact_brief(
                snapshot.job_facts,
                query=" ".join(profile.competencies),
                preferred_ids=profile.basis_fact_ids,
            )
        )
    if snapshot.job_mode is JobMode.NONE:
        area = snapshot.area
        target = f"{area.area} ({area.seniority})" if area else "the candidate's own field"
        return (
            "There is no job offer. This is a getting-to-know interview for a generic company "
            f"working in {target}, the area inferred from the candidate's documents."
        )
    lines = []
    if snapshot.job_mode is JobMode.GENERATED:
        lines.append(
            "The job offer below was drafted from the candidate's description of the position; "
            "it is not a real posting."
        )
    lines.append(_facts_by_kind(snapshot.job_facts))
    by_id = {f.id: f for f in snapshot.job_facts}
    missing = [
        by_id[m.requirement_id].text
        for m in snapshot.matches
        if m.status is MatchStatus.NOT_SHOWN and m.requirement_id in by_id
    ]
    partial = [
        by_id[m.requirement_id].text
        for m in snapshot.matches
        if m.status is MatchStatus.PARTIAL and m.requirement_id in by_id
    ]
    if missing:
        lines.append("Requirements the candidate's documents do not show:")
        lines += [f"- {text}" for text in missing]
    if partial:
        lines.append("Requirements the documents show only in part:")
        lines += [f"- {text}" for text in partial]
    return _limit("\n".join(lines))


def vocabulary_prompt(vocabulary: tuple[str, ...], max_chars: int = 500) -> str | None:
    """The technical terms as a recogniser prompt: the most frequent first, within a budget."""
    out: list[str] = []
    size = 0
    for term in vocabulary:
        if size + len(term) + 2 > max_chars:
            break
        out.append(term)
        size += len(term) + 2
    return ", ".join(out) or None


def _facts_by_kind(facts: tuple[Fact, ...]) -> str:
    lines = []
    for kind in _KIND_ORDER:
        group = [f for f in facts if f.kind is kind]
        if not group:
            continue
        lines.append(f"{kind.value.replace('_', ' ').capitalize()}:")
        for fact in group:
            note = "" if fact.origin is FactOrigin.DECLARED else f" ({_ORIGIN_LABELS[fact.origin]})"
            if fact.review is Review.CORRECTED:
                note = " (corrected by the candidate)"
            lines.append(f"- {fact.text}{note}")
    return "\n".join(lines)


def _limit(text: str) -> str:
    if len(text) <= MAX_BRIEF_CHARS:
        return text
    cut = text[:MAX_BRIEF_CHARS].rsplit("\n", 1)[0]
    return cut + "\n- (more facts omitted)"


def selected_fact_brief(
    facts: tuple[Fact, ...],
    *,
    query: str = "",
    preferred_ids: tuple[str, ...] = (),
    max_chars: int = MAX_BRIEF_CHARS,
) -> str:
    """Select whole facts by objective links and lexical relevance, retaining source ids.

    The full fact collection stays in the session for later turns. Selection does not change
    a fact's provenance or turn a model interpretation into a documented candidate claim.
    """
    selected = select_facts(facts, query=query, preferred_ids=preferred_ids, max_chars=max_chars)
    return "\n".join(_fact_line(f) for f in selected) or "No relevant facts available."


def _fact_line(fact: Fact) -> str:
    return f"[{fact.id}; {fact.origin.value}; document={fact.document_id or 'user'}] {fact.text}"


def select_facts(
    facts: tuple[Fact, ...],
    *,
    query: str = "",
    preferred_ids: tuple[str, ...] = (),
    max_chars: int = MAX_BRIEF_CHARS,
) -> tuple[Fact, ...]:
    """Whole facts within a context budget; the source collection is never truncated."""
    words = set(re.findall(r"\w{4,}", query.casefold()))
    preferred = set(preferred_ids)
    ranked = sorted(
        enumerate(facts),
        key=lambda pair: (
            pair[1].id not in preferred,
            -len(words & set(re.findall(r"\w{4,}", pair[1].text.casefold()))),
            pair[0],
        ),
    )
    selected: list[Fact] = []
    size = 0
    for _, fact in ranked:
        length = len(_fact_line(fact)) + 1
        if size + length <= max_chars:
            selected.append(fact)
            size += length
    return tuple(selected)
