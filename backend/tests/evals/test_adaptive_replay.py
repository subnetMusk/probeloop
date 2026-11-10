from dataclasses import replace

import pytest
from evals.adaptive_replay import fingerprint, paired_session, replay_metrics, validate_audit

from tests.assessment.test_adaptive_assessment import session


def test_audit_requires_exact_context_and_persona_confirmation() -> None:
    current = session()
    digest = fingerprint(current, None)
    audit = {
        "synthetic": True,
        "sessions": {
            current.id: {
                "fingerprint": digest,
                "persona_coherent": True,
                "sources": ["https://example.test/source"],
            }
        },
    }
    assert validate_audit(audit, current, digest)["persona_coherent"] is True
    with pytest.raises(ValueError, match="source-audited"):
        validate_audit(audit, current, "modified")
    audit["synthetic"] = False
    with pytest.raises(ValueError, match="source-audited"):
        validate_audit(audit, current, digest)


def test_fingerprint_changes_with_target_expectations() -> None:
    current = session()
    before = fingerprint(current, None)
    profile = current.context.role_profile
    assert profile is not None
    current.context = replace(current.context, role_profile=replace(profile, seniority="Senior"))
    assert fingerprint(current, None) != before


def test_controlled_pair_keeps_only_the_first_question_without_mutating_source() -> None:
    current = session()
    before = fingerprint(current, None)
    contrast = paired_session(current, "weak", "A generated contrast answer.")
    assert len(contrast.turns) == 2
    assert contrast.interviewer_turns()[0] == current.interviewer_turns()[0]
    assert contrast.candidate_turns()[0].text == "A generated contrast answer."
    assert contrast.context == current.context
    assert contrast.is_terminal
    assert fingerprint(current, None) == before


def test_metrics_keep_missing_verification_and_missing_scores_unknown() -> None:
    row = {
        "profile": "local",
        "session_id": "synthetic",
        "mean": None,
        "judgement": {"scores": [], "observations": []},
    }
    profile = replay_metrics([row])["profiles"]["local"]
    assert profile["unverified"] is None
    assert profile["max_mean_spread"] is None
    assert profile["ranking"] is None
    assert profile["detection"] is None
