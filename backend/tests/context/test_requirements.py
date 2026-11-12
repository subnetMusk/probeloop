from __future__ import annotations

from dataclasses import replace

import pytest

from probeloop.context.application.snapshots import snapshot_of
from probeloop.context.domain.model import (
    Alternative,
    ContextError,
    FactKind,
    Obligation,
    RequirementDetail,
    Route,
    Threshold,
    decide_obligation,
)
from probeloop.storage.sql_context import fact_from_json, fact_to_json
from tests.context.test_preparation import in_review

MUST, PREFERRED, UNCLEAR = Obligation.MUST, Obligation.PREFERRED, Obligation.UNCLEAR
DETAIL = RequirementDetail(
    obligation=MUST,
    cue="Requisiti",
    category="experience",
    any_of=(Alternative("Python"), Alternative("another backend language", open=True)),
    equivalents=(Route("experience", "equivalent experience"),),
    threshold=Threshold("years", "5", "backend development"),
    readings=(("cue", MUST), ("jev", MUST), ("model", PREFERRED)),
)


def test_the_strongest_source_that_decides_wins() -> None:
    assert decide_obligation((("model", PREFERRED), ("cue", MUST))) is MUST
    assert decide_obligation((("cue", UNCLEAR), ("jev", PREFERRED), ("model", MUST))) is PREFERRED
    assert decide_obligation((("jev", UNCLEAR), ("model", UNCLEAR))) is UNCLEAR
    assert decide_obligation(()) is UNCLEAR


def test_disagreement_is_disputed_until_the_user_decides() -> None:
    assert DETAIL.disputed
    assert not replace(DETAIL, readings=(("cue", MUST), ("jev", UNCLEAR))).disputed
    settled = replace(DETAIL, readings=(*DETAIL.readings, ("user", PREFERRED)))
    assert not settled.disputed


def test_structure_values_are_checked() -> None:
    with pytest.raises(ContextError, match="category"):
        replace(DETAIL, category="hobby")
    with pytest.raises(ContextError, match="route"):
        Route("luck", "x")
    with pytest.raises(ContextError, match="threshold"):
        Threshold("height", "2")
    with pytest.raises(ContextError, match="source"):
        replace(DETAIL, readings=(("guess", MUST),))


def test_the_user_sets_the_obligation_and_the_kind_follows() -> None:
    p = in_review()
    p.facts = [replace(f, requirement=DETAIL) if f.id == "r1" else f for f in p.facts]

    updated = p.set_obligation("r1", PREFERRED)

    assert updated.kind is FactKind.NICE_TO_HAVE
    assert updated.requirement is not None
    assert updated.requirement.obligation is PREFERRED
    assert updated.requirement.readings[-1] == ("user", PREFERRED)
    assert not updated.requirement.disputed
    again = p.set_obligation("r1", MUST)
    assert again.requirement is not None
    assert [r for r in again.requirement.readings if r[0] == "user"] == [("user", MUST)]
    with pytest.raises(ContextError, match="only a requirement"):
        p.set_obligation("f1", MUST)


def test_the_detail_is_stored_and_old_facts_still_load() -> None:
    fact = replace(in_review().fact("r1"), requirement=DETAIL)
    assert fact_from_json(fact_to_json(fact)) == fact
    old = fact_to_json(in_review().fact("r2"))
    del old["requirement"]
    assert fact_from_json(old).requirement is None


def test_the_structure_changes_the_snapshot_but_the_readings_do_not() -> None:
    def snapshot_hash(detail: RequirementDetail) -> str:
        p = in_review()
        p.facts = [replace(f, requirement=detail) if f.id == "r1" else f for f in p.facts]
        return snapshot_of(p, "s", 0).content_hash

    base = snapshot_hash(DETAIL)
    assert snapshot_hash(replace(DETAIL, readings=(("cue", MUST),))) == base
    assert snapshot_hash(replace(DETAIL, threshold=Threshold("years", "3"))) != base
    assert snapshot_hash(replace(DETAIL, obligation=PREFERRED)) != base
