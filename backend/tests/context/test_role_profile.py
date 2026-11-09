from dataclasses import replace

import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.context.application.analysis import ContextAnalyser
from probeloop.context.application.snapshots import selected_fact_brief, snapshot_of
from probeloop.context.domain.model import ContextError, RoleProfile
from tests.context.test_preparation import GUESS, ROLE, in_review


def test_confirmed_profiles_require_explicit_role_and_level() -> None:
    with pytest.raises(ContextError, match="seniority"):
        RoleProfile(profession="Medicine", target_role="Internal medicine trainee", confirmed=True)
    profile = RoleProfile(
        "Medicine", "Internal medicine trainee", "CT1 under supervision", confirmed=True
    )
    preparation = in_review()
    preparation.role_profile = RoleProfile()
    with pytest.raises(ContextError, match="confirm the target"):
        preparation.approve("s")
    preparation.set_role_profile(profile)
    preparation.approve("s")


def test_role_level_changes_snapshot_identity_without_changing_difficulty() -> None:
    preparation = in_review()
    profile = RoleProfile("Economics", "Economist", "junior", confirmed=True)
    preparation.set_role_profile(profile)
    first = snapshot_of(preparation, "s1", 0)
    preparation.set_role_profile(replace(profile, seniority="senior"))
    second = snapshot_of(preparation, "s2", 1)
    assert first.content_hash != second.content_hash
    assert first.role_profile is not None
    assert first.role_profile.seniority == "junior"
    with pytest.raises(ContextError, match="unavailable fact"):
        preparation.set_role_profile(
            RoleProfile(
                "Teaching", "Teacher", "trainee", basis_fact_ids=("invented",), confirmed=True
            )
        )


def test_context_selection_preserves_whole_fact_provenance_and_prioritizes_links() -> None:
    late = replace(ROLE, id="late", statement="A supervised economics research project.")
    facts = tuple(replace(ROLE, id=str(i), statement="Unrelated history " * 15) for i in range(30))
    selected = selected_fact_brief((*facts, late), preferred_ids=("late",), max_chars=200)
    assert selected.startswith("[late; declared;")
    assert late.text in selected
    assert "Unrelated history" not in selected
    assert len(facts) == 30  # selection does not erase the source collection


async def test_proposals_cannot_cite_unknown_or_inferred_facts() -> None:
    import json

    model = FakeChatModel(
        [
            json.dumps(
                {
                    "profession": "Economics",
                    "target_role": "Research economist",
                    "seniority": "junior",
                    "responsibilities": [],
                    "competencies": ["Economic reasoning"],
                    "basis_fact_ids": [ROLE.id, GUESS.id, "invented"],
                    "rationale": "A proposal to review.",
                }
            )
        ]
    )
    proposal = await ContextAnalyser(model).propose_role([ROLE, GUESS], "en")
    assert proposal.basis_fact_ids == (ROLE.id,)
    assert not proposal.confirmed
    assert GUESS.statement not in model.requests[0].messages[0].content
