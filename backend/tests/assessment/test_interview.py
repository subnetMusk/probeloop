from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Any

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import ChatRequest
from probeloop.assessment.application.evidence import Source, checked_evidence, source_span
from probeloop.assessment.application.interview_review import (
    InterviewJudgement,
    InterviewReviewer,
    evaluation_context,
)
from probeloop.assessment.application.schemas import EvidenceData
from probeloop.assessment.application.segmentation import KindsOut, answer_units, classified
from probeloop.assessment.domain.model import Evidence, Score
from probeloop.assessment.domain.units import aggregate_scores, paired_scores
from probeloop.context.application.snapshots import snapshot_of
from tests.assessment.support import synthetic_session
from tests.context.test_preparation import in_review


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
        {
            "units": [
                {"unit_id": "u0", "kind": "behavioral", "past_example": True},
                {"unit_id": "u8", "kind": "technical", "past_example": False},
            ]
        }
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
    second = replace(first, value=5, reason="A second reason that must not be repeated.")
    paired = paired_scores((first,), (second,))[0]
    assert paired.value == 3
    assert paired.unstable
    assert paired.reason == first.reason
    missing = paired_scores((first,), (replace(second, value=None),))[0]
    assert missing.value is None
    assert missing.reason == first.reason
    aggregate = aggregate_scores(
        (
            paired,
            replace(paired, value=5, unit_id="u2"),
            replace(first, criterion_id="technical.depth", value=2),
        )
    )
    assert [s.value for s in aggregate] == [4, 2]
    assert aggregate[0].reason == "2/2"


def _script(
    verdicts: dict[str, str], synthesis: list[str], values: tuple[int, int] = (3, 5)
) -> Callable[[ChatRequest], str]:
    """A model that behaves like the observed evaluator, including its known mistakes."""

    def script(request: ChatRequest) -> str:
        data = json.loads(request.messages[0].content)
        if isinstance(data, list):
            return json.dumps(
                {
                    "units": [
                        {
                            "unit_id": u["unit_id"],
                            "kind": "behavioral" if u["unit_id"] == "u0" else "technical",
                            "past_example": u["unit_id"] != "u6",
                        }
                        for u in data
                    ]
                }
            )
        if "statement" in data:
            verdict = next(v for k, v in verdicts.items() if k in data["statement"])
            return json.dumps({"analysis": "Checked.", "verdict": verdict})
        if "observations" in data:
            return json.dumps(
                {"priorities": synthesis, "strengths": [], "summary": "Practise ownership."}
            )
        unit = data["unit"]
        turn = next(t for t in unit["turns"] if t["speaker"] == "candidate")
        reverse = data["rubric"]["anchor_order"] == "descending"
        evidence = [{"source_id": turn["source_id"], "quote": turn["text"]}]
        scores = {
            c["id"]: {
                "evidence": evidence,
                "reason": "Observable evidence.",
                "score": values[1] if reverse else values[0],
            }
            for c in data["rubric"]["criteria"]
        }
        result: dict[str, Any] = {"scores": scores}
        if unit["unit_id"] == "u4":
            # Interviewer text is never evidence.
            scores["accuracy"]["evidence"] = [
                {"source_id": "turn-4", "quote": "How does a PostgreSQL index affect writes?"}
            ]
        if "observations" in (request.response_schema or {})["properties"]:
            notes = [{"kind": "improvement", "evidence": evidence, "text": "Be specific."}]
            if unit["kind"] == "behavioral":
                notes.append(
                    {"kind": "technical_error", "evidence": evidence, "text": "A red flag."}
                )
            if unit["kind"] == "technical":
                notes.append(
                    {"kind": "technical_error", "evidence": evidence, "text": "Model correction."}
                )
                if unit["unit_id"] == "u4":
                    notes.append(
                        {
                            "kind": "technical_error",
                            "evidence": evidence,
                            "text": "Same quote again.",
                        }
                    )
            result["observations"] = notes
            result["coverage"] = []
        return json.dumps(result)

    return script


AGREE = {"index always": "incorrect", "invalid index": "incorrect"}


async def _review(model: FakeChatModel, **options: Any) -> InterviewJudgement:
    async def progress(value: float, message: str | None) -> None:
        pass

    return await InterviewReviewer(model, **options).review(
        synthetic_session(), None, "en", progress
    )


def _judges(model: FakeChatModel) -> list[ChatRequest]:
    return [r for r in model.requests if "approved_context" in r.messages[0].content]


async def test_pipeline_pairs_anchor_orders_and_discards_interviewer_evidence() -> None:
    model = FakeChatModel([_script(AGREE, ["o1"])])
    result = await _review(model)
    assert len(result.units) == 4
    assert result.units[-1].kind == "logistics"
    accuracy = [s for s in result.unit_scores if s.criterion_id == "technical.accuracy"]
    assert [s.value for s in accuracy] == [None, 4]
    # The u6 question asks for a plan: experience is not assessable, whatever the judge scored.
    experience = {s.unit_id: s for s in result.unit_scores if s.criterion_id.endswith("experience")}
    assert experience["u4"].value == 4
    assert experience["u6"].value is None
    assert experience["u6"].evidence == ()
    assert experience["u6"].reason == "No question asked for a past example."
    assert all(s.value == 4 for s in result.unit_scores if s.value is not None)
    assert all(s.unstable for s in result.unit_scores if s.value is not None)
    assert all(r.reasoning == "off" for r in model.requests)
    # Only the ascending pass returns observations; the descending one exists for the scores.
    judges = _judges(model)
    assert len(judges) == 6
    for request in judges:
        data = json.loads(request.messages[0].content)
        properties = (request.response_schema or {})["properties"]
        ascending = data["rubric"]["anchor_order"] == "ascending"
        assert ("observations" in properties) == ascending
        anchors = [list(c["anchors"]) for c in data["rubric"]["criteria"]]
        assert all(a == (["1", "3", "5"] if ascending else ["5", "3", "1"]) for a in anchors)
    assert [c.phase for c in result.calls] == [
        "classify",
        "judge_ascending",
        "judge_descending",
        "judge_ascending",
        "judge_descending",
        "check_claim",
        "judge_ascending",
        "judge_descending",
        "check_claim",
        "synthesise",
    ]
    assert all(c.attempts == 1 for c in result.calls)


async def test_judging_requests_share_the_context_prefix_and_see_only_their_unit() -> None:
    model = FakeChatModel([_script(AGREE, ["o1"])])
    await _review(model)
    judges = _judges(model)
    assert len({r.messages[0].content.split('"rubric"')[0] for r in judges}) == 1
    assert len({r.instructions for r in judges}) == 1
    units = [json.loads(r.messages[0].content)["unit"] for r in judges]
    assert all(set(u) == {"unit_id", "kind", "topic", "difficulty", "turns"} for u in units)
    assert {t["seq"] for t in units[2]["turns"]} == {4, 5}


async def test_a_disputed_correction_is_withheld_and_marks_accuracy_unstable() -> None:
    verdicts = {"index always": "incorrect", "invalid index": "correct"}
    model = FakeChatModel([_script(verdicts, ["o1", "o99"], values=(4, 4))])
    result = await _review(model)
    unstable = {(s.unit_id, s.criterion_id) for s in result.unit_scores if s.unstable}
    assert unstable == {("u6", "technical.accuracy")}
    errors = [o for o in result.observations if o.kind == "technical_error"]
    assert [o.unit_id for o in errors] == ["u4"]
    assert result.disputed == 1
    # The repeated correction on the same quotation is checked once and shown once.
    assert len([c for c in result.calls if c.phase == "check_claim"]) == 2
    claims = [r for r in model.requests if '"statement"' in r.messages[0].content]
    assert claims
    assert all("Model correction" not in r.messages[0].content for r in claims)
    # The summary references existing observations instead of copying them.
    assert result.observations[0].kind == "summary"
    assert result.observations[0].evidence == result.observations[1].evidence
    assert len(result.observations) == len(set(result.observations))


async def test_a_summary_without_valid_references_is_not_shown() -> None:
    result = await _review(FakeChatModel([_script(AGREE, ["o42"])]))
    assert result.observations
    assert all(o.kind != "summary" for o in result.observations)


async def test_thinking_for_judges_is_an_explicit_recorded_choice() -> None:
    model = FakeChatModel([_script(AGREE, ["o1"])])
    assert ":think+" in InterviewReviewer(model, judge_reasoning="default").prompt_ref
    assert ":off+" in InterviewReviewer(model).prompt_ref
    await _review(model, judge_reasoning="default")
    judges = _judges(model)
    assert all(r.reasoning == "default" for r in judges)
    assert all((r.max_output_tokens or 0) > 7000 for r in judges)
    others = [r for r in model.requests if r not in judges]
    assert others
    assert all(r.reasoning == "off" for r in others)


def test_the_evaluation_context_sends_documents_once_without_metadata() -> None:
    snapshot = snapshot_of(in_review(), "snapshot", 0)
    context = evaluation_context(synthetic_session(), snapshot)
    text = json.dumps(context, ensure_ascii=False)
    for document in snapshot.documents:
        assert text.count(json.dumps(document.text, ensure_ascii=False)[1:-1]) == 1
    for key in ("created_at", "sha256", "quote", "origin", "content_hash", "rationale"):
        assert f'"{key}"' not in text
    requirements = context["requirements"]
    assert isinstance(requirements, list)
    assert {r["id"]: r["cv_match"] for r in requirements} == {"r1": "partial", "r2": "not_shown"}
    assert len(text) < len(json.dumps(asdict(snapshot), ensure_ascii=False))


async def test_evaluator_requests_disable_the_presence_penalty_and_band_scores() -> None:
    model = FakeChatModel([_script(AGREE, ["o1"])])
    await _review(model)
    assert all(r.presence_penalty == 0.0 for r in model.requests)
    synthesis = json.loads(model.requests[-1].messages[0].content)
    bands = {s["criterion_id"]: s["band"] for s in synthesis["scores"]}
    assert bands["technical.accuracy"] == "strong"
    model = FakeChatModel([_script(AGREE, ["o1"], values=(1, 2))])
    await _review(model, presence_penalty=None)
    assert all(r.presence_penalty is None for r in model.requests)
    synthesis = json.loads(model.requests[-1].messages[0].content)
    assert {s["band"] for s in synthesis["scores"]} <= {"weak", "not assessable"}


def test_verified_quotations_are_shown_as_the_source_writes_them() -> None:
    text = "I would measure query plans and write load first. Concurrent index creation..."
    sources = {"turn-7": Source(text, 7)}
    evidence = checked_evidence(
        [
            EvidenceData(
                source_id="turn-7", quote="i would MEASURE query plans and write load first..."
            ),
            EvidenceData(source_id="turn-7", quote="first concurrent index"),
        ],
        sources,
    )
    assert [e.quote for e in evidence] == [
        "I would measure query plans and write load first",
        "first. Concurrent index",
    ]
    assert source_span("plans and write load", "Plans, and write-load.") == "Plans, and write-load"
    assert source_span("not in the text at all", text) is None


def test_an_elided_quotation_is_kept_only_when_every_part_is_verbatim() -> None:
    text = (
        "The team decided to introduce a partial index on the status column. Then, after a "
        "week of tests, the team opted for GiST because lookups were composite."
    )
    sources = {"turn-1": Source(text, 1)}

    def quoted(quote: str) -> list[str]:
        items = [EvidenceData(source_id="turn-1", quote=quote)]
        return [e.quote for e in checked_evidence(items, sources)]

    assert quoted("introduce a partial index... the team opted for GiST…") == [
        "introduce a partial index",
        "the team opted for GiST",
    ]
    # An invented part, or a part too short to locate, rejects the whole quotation.
    assert quoted("introduce a partial index... the team chose BRIN") == []
    assert quoted("introduce a partial index... GiST") == []


def test_the_past_example_flag_is_decided_before_the_unit_kind() -> None:
    # Constrained decoding follows the schema's property order. Deciding the kind first made the
    # flag false for technical questions that also ask for a personal example.
    unit = KindsOut.model_json_schema()["$defs"]["KindOut"]
    assert list(unit["properties"]) == ["unit_id", "past_example", "kind"]
