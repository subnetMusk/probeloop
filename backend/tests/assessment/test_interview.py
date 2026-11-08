from __future__ import annotations

import json
from dataclasses import replace

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import ChatRequest
from probeloop.assessment.application.evidence import Source, checked_evidence
from probeloop.assessment.application.interview_review import InterviewReviewer
from probeloop.assessment.application.rubrics import load_rubric
from probeloop.assessment.application.schemas import EvidenceData
from probeloop.assessment.application.segmentation import KindsOut, answer_units, classified
from probeloop.assessment.domain.model import Evidence, Score
from probeloop.assessment.domain.units import aggregate_scores, paired_scores
from tests.assessment.support import synthetic_session


def test_turn_identity_comes_from_verified_sources_and_conflicts_are_rejected() -> None:
    sources = {"turn-7": Source("I tested the rollback procedure.", 7)}
    inferred = checked_evidence(
        [EvidenceData(source_id="turn-7", quote="tested the rollback procedure")], sources
    )
    assert inferred[0].turn_seq == 7
    assert (
        checked_evidence(
            [EvidenceData(source_id="turn-7", quote="tested the rollback procedure", turn_seq=8)],
            sources,
        )
        == ()
    )


def test_followups_group_and_closing_is_never_scored() -> None:
    units = answer_units(synthetic_session())
    assert units[0].question_seqs == (0, 2)
    assert units[0].answer_seqs == (1, 3)
    assert units[-1].kind == "logistics"
    output = KindsOut.model_validate(
        {"units": [{"unit_id": "u0", "kind": "behavioral"}, {"unit_id": "u8", "kind": "technical"}]}
    )
    result = classified(units, output)
    assert result[0].kind == "behavioral"
    assert result[1].kind == "unclassified"
    assert result[-1].kind == "logistics"


def test_anchor_disagreement_missing_values_and_equal_criterion_weights() -> None:
    first = Score(
        "technical.accuracy",
        "Accuracy",
        1,
        "x",
        (Evidence("turn-1", "A wrong statement", 1),),
        unit_id="u0",
    )
    second = replace(first, value=5)
    paired = paired_scores((first,), (second,))[0]
    assert paired.value == 3
    assert paired.unstable
    missing = paired_scores((first,), (replace(second, value=None),))[0]
    assert missing.value is None
    aggregate = aggregate_scores(
        (
            paired,
            replace(paired, value=5, unit_id="u2"),
            replace(first, criterion_id="technical.depth", value=2),
        )
    )
    assert [s.value for s in aggregate] == [4, 2]
    assert aggregate[0].reason == "2/2"


async def test_pipeline_reverses_anchors_and_discards_invented_and_interviewer_evidence() -> None:
    def script(request: ChatRequest) -> str:
        data = json.loads(request.messages[0].content)
        if isinstance(data, list):
            return json.dumps(
                {
                    "units": [
                        {
                            "unit_id": u["unit_id"],
                            "kind": "behavioral" if u["unit_id"] == "u0" else "technical",
                        }
                        for u in data
                    ]
                }
            )
        if "kind" not in data:
            return json.dumps(
                {
                    "scores": [],
                    "observations": [
                        {
                            "kind": "summary",
                            "text": "Invented.",
                            "evidence": [
                                {
                                    "source_id": "turn-1",
                                    "turn_seq": 1,
                                    "quote": "I managed fifty engineers.",
                                }
                            ],
                        }
                    ],
                }
            )
        turn = next(t for t in data["turns"] if t["speaker"] == "candidate")
        reverse = request.instructions.index("5:") < request.instructions.index("1:")
        evidence = [
            {"source_id": turn["source_id"], "turn_seq": turn["seq"], "quote": turn["text"]}
        ]
        scores = [
            {
                "criterion_id": c.id,
                "score": 5 if reverse else 3,
                "reason": "Observable evidence.",
                "evidence": evidence,
            }
            for c in load_rubric(data["kind"]).criteria
        ]
        if data["kind"] == "technical":
            scores[0]["evidence"] = [
                {
                    "source_id": "turn-4",
                    "turn_seq": 4,
                    "quote": "How does a PostgreSQL index affect writes?",
                }
            ]
        return json.dumps({"scores": scores, "observations": []})

    model = FakeChatModel([script])

    async def progress(value: float, message: str | None) -> None:
        pass

    result = await InterviewReviewer(model).review(synthetic_session(), None, "en", progress)
    assert len(result.units) == 4
    assert result.units[-1].kind == "logistics"
    assert all(
        s.value is None for s in result.unit_scores if s.criterion_id == "technical.accuracy"
    )
    assert all(s.value == 4 and s.unstable for s in result.unit_scores if s.value is not None)
    assert not result.observations
    assert result.dropped >= 5
    assert all(
        r.reasoning == "default" for r in model.requests if "Assess this answer" in r.instructions
    )
    assert all(
        r.reasoning == "off" for r in model.requests if "Assess this answer" not in r.instructions
    )
    assert len([r for r in model.requests if "Assess this answer" in r.instructions]) == 6
