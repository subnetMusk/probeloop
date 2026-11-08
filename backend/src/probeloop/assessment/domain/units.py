"""Observable answer units and deterministic score aggregation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from probeloop.assessment.domain.model import Score


def paired_scores(first: tuple[Score, ...], second: tuple[Score, ...]) -> tuple[Score, ...]:
    """Both anchor orders must support a score; a missing judgement is never imputed."""
    other = {s.criterion_id: s for s in second}
    paired = []
    for score in first:
        reverse = other[score.criterion_id]
        if score.value is None or reverse.value is None:
            paired.append(
                replace(
                    score,
                    value=None,
                    reason=reverse.reason if reverse.value is None else score.reason,
                )
            )
        else:
            paired.append(
                replace(
                    score,
                    value=(score.value + reverse.value) / 2,
                    reason="\n".join(dict.fromkeys((score.reason, reverse.reason))),
                    evidence=tuple(dict.fromkeys((*score.evidence, *reverse.evidence))),
                    unstable=abs(score.value - reverse.value) >= 2,
                )
            )
    return tuple(paired)


def aggregate_scores(scores: tuple[Score, ...]) -> tuple[Score, ...]:
    """Equal answer weights within each namespaced criterion, then equal criterion weights."""
    grouped: dict[str, list[Score]] = defaultdict(list)
    for score in scores:
        grouped[score.criterion_id].append(score)
    result = []
    for criterion_id, items in grouped.items():
        available = [s for s in items if s.value is not None]
        values = [s.value for s in available if s.value is not None]
        result.append(
            Score(
                criterion_id,
                items[0].label,
                round(sum(values) / len(values), 2) if values else None,
                f"{len(available)}/{len(items)}",
                tuple(dict.fromkeys(e for s in available for e in s.evidence)),
                any(s.unstable for s in available),
            )
        )
    return tuple(result)
