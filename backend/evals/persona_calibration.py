"""Calibrate the interview evaluator with LLM personas built from labelled topic cards.

For each card in `fixtures/synthetic/assessment/personas.json` a persona model answers the
card's question twice, live: a weak persona that states the card's wrong claim and describes
the work only as the team's, and a strong persona that is correct and gives a concrete
first-hand account. Answers are generated, never prewritten. The evaluator then reviews each
answer several times. Thresholds from proposal section 6:

- planted problems detected >= 80% (the wrong claim and the vague ownership of weak answers);
- strong answers ranked above weak ones in >= 90% of pairs;
- zero unverified quotations;
- score spread <= 0.5 over the regenerations of the same answer.

Corrections on strong answers, discarded items and criterion coverage are recorded too. A
correction on a generated strong answer needs adjudication: its label does not prove every claim.
A persona answer is generated again, up to three times, until its traits can be checked in code:
a weak answer contains the wrong claim verbatim, no first-person "I" and no numbers; a strong
answer contains "I" and not the wrong claim. Answers that never comply are excluded and listed.
With one scored unit per answer, the "overall" of an answer is the mean of its available unit
scores. Everything is synthetic; keep the output outside git.

    python -m evals.persona_calibration --output /out/calibration.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz
from tests.conftest import make_session

from probeloop.ai.debuglog import DebugLogChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest
from probeloop.assessment.application.interview_review import InterviewJudgement, InterviewReviewer
from probeloop.bootstrap import build
from probeloop.context.application.analysis import normalise
from probeloop.interview.domain.model import (
    EndReason,
    InterviewerMove,
    InterviewSession,
    MoveAction,
)
from probeloop.settings import Settings

CARDS = Path(__file__).parent / "fixtures/synthetic/assessment/personas.json"
THRESHOLDS = {"detection": 0.8, "ranking": 0.9, "unverified": 0, "spread": 0.5}
ATTEMPTS = 3
BENCHMARK_REF = "personas@v3:technical-ownership"
_FIRST_PERSON = re.compile(r"\bI\b")
_DIGIT = re.compile(r"\d")

PERSONA_PROMPT = """You play a job candidate in a practice interview for an automated test.
Answer the interviewer's question in English, in 90 to 160 words, as natural spoken text
without lists or headings. Never mention that you are playing a role or that this is a test.
Traits of this answer:
{traits}"""

TRAITS = {
    "weak": (
        "- Include this deliberately planted false sentence word for word and assert it as fact: "
        "{wrong_claim}\n"
        "- Keep the mistaken belief throughout the answer: do not retract, correct, contradict "
        "or qualify it, and do not explain the correct alternative.\n"
        "- Describe the work only as what 'we' or 'the team' did: no decision of your own, no "
        "constraint, no alternative and no concrete outcome.\n"
        "- Give no numbers, percentages or measurements."
    ),
    "strong": (
        "- Be technically correct and consistent with: {correct_fact}\n"
        "- Describe one specific situation you handled yourself: the constraints, an alternative "
        "you rejected and why, and a concrete outcome.\n"
        "- Identify a decision you made and a check you personally performed, distinguishing "
        "your responsibility from colleagues' work.\n"
        "- Do not add unconditional technical claims beyond the supplied fact."
    ),
}


@dataclass(frozen=True)
class Answer:
    card: str
    persona: str
    question: str
    text: str
    compliant: bool
    attempts: int


@dataclass(frozen=True)
class Assessment:
    card: str
    persona: str
    regeneration: int
    mean: float | None
    accuracy: float | None
    experience: float | None
    ownership: float | None
    corrections: tuple[str, ...]
    unverified: int
    assessed: int
    criteria: int
    dropped: int
    duration_s: float


def session_for(question: str, answer: str) -> InterviewSession:
    session = make_session()
    session.start(0)
    for index, (action, utterance, reply) in enumerate(
        (
            (MoveAction.NEW_TOPIC, question, answer),
            (MoveAction.WRAP_UP, "Do you have any questions for us?", "No, thank you."),
        )
    ):
        now = index * 120.0
        session.record_move(InterviewerMove(action, "t1", utterance), now)
        session.finish_speaking(now + 5)
        session.start_answer(now + 7)
        session.finish_answer(now + 60)
        session.record_answer(reply, now + 61)
    session.end(EndReason.USER_ENDED, 300)
    return session


def contains(text: str, claim: str) -> bool:
    return normalise(claim).rstrip(".") in normalise(text)


def traits_present(text: str, card: dict[str, str], persona: str) -> bool:
    claimed = contains(text, card["wrong_claim"])
    first_person = _FIRST_PERSON.search(text) is not None
    if persona == "weak":
        return claimed and not first_person and _DIGIT.search(text) is None
    return first_person and not claimed


def assessment_of(
    answer: Answer, regeneration: int, result: InterviewJudgement, duration_s: float
) -> Assessment:
    session_text = normalise(answer.text)

    def score(criterion: str) -> float | None:
        return next((s.value for s in result.unit_scores if s.criterion_id == criterion), None)

    values = [s.value for s in result.unit_scores if s.value is not None]
    quotes = [e.quote for s in result.unit_scores for e in s.evidence] + [
        e.quote for o in result.observations for e in o.evidence
    ]
    return Assessment(
        card=answer.card,
        persona=answer.persona,
        regeneration=regeneration,
        mean=round(statistics.fmean(values), 2) if values else None,
        accuracy=score("technical.accuracy"),
        experience=score("technical.experience"),
        ownership=score("technical.ownership"),
        corrections=tuple(
            " … ".join(e.quote for e in o.evidence)
            for o in result.observations
            if o.kind == "technical_error"
        ),
        # The candidate's last answer is the wrap-up reply, which is never quoted as evidence.
        unverified=sum(normalise(q) not in session_text for q in quotes),
        assessed=sum(s.value is not None for s in result.unit_scores),
        criteria=len(result.unit_scores),
        dropped=result.dropped,
        duration_s=round(duration_s, 2),
    )


def summary(
    answers: list[Answer], assessments: list[Assessment], wrong_claims: dict[str, str]
) -> dict[str, Any]:
    weak = [a for a in assessments if a.persona == "weak"]
    usable = {(a.card, a.persona) for a in answers if a.compliant}
    technical_detected = ownership_detected = possible = 0
    for item in weak:
        if (item.card, "weak") not in usable:
            continue
        claim = wrong_claims[item.card]
        flagged = any(
            fuzz.partial_ratio(normalise(q), normalise(claim)) >= 85 for q in item.corrections
        )
        technical_detected += flagged or (item.accuracy is not None and item.accuracy <= 2)
        ownership_detected += item.ownership is not None and item.ownership <= 2
        possible += 1
    pairs = ranked = 0
    by_key = {(a.card, a.persona, a.regeneration): a for a in assessments}
    for item in weak:
        strong = by_key.get((item.card, "strong", item.regeneration))
        if strong is None or not {(item.card, "weak"), (item.card, "strong")} <= usable:
            continue
        pairs += 1
        ranked += strong.mean is not None and item.mean is not None and strong.mean > item.mean
    spreads = {}
    for card, persona in {(a.card, a.persona) for a in assessments}:
        means = [a.mean for a in assessments if (a.card, a.persona) == (card, persona)]
        known = [m for m in means if m is not None]
        spreads[f"{card}/{persona}"] = (
            round(max(known) - min(known), 2) if len(known) == len(means) and known else None
        )
    result: dict[str, Any] = {
        "detection": round((technical_detected + ownership_detected) / (2 * possible), 3)
        if possible
        else None,
        "technical_detection": round(technical_detected / possible, 3) if possible else None,
        "ownership_detection": round(ownership_detected / possible, 3) if possible else None,
        "ranking": round(ranked / pairs, 3) if pairs else None,
        "unverified": sum(a.unverified for a in assessments),
        "spread": max((s for s in spreads.values() if s is not None), default=None),
        "spreads": spreads,
        "corrections_on_strong": sum(
            len(a.corrections) for a in assessments if a.persona == "strong"
        ),
        "non_compliant": sorted(f"{a.card}/{a.persona}" for a in answers if not a.compliant),
        "persona_attempts": sum(a.attempts for a in answers),
        "coverage": round(
            sum(a.assessed for a in assessments) / max(1, sum(a.criteria for a in assessments)), 3
        ),
        "dropped": sum(a.dropped for a in assessments),
        "median_review_s": statistics.median([a.duration_s for a in assessments])
        if assessments
        else None,
    }
    result["passed"] = (
        result["detection"] is not None
        and result["detection"] >= THRESHOLDS["detection"]
        and result["ranking"] is not None
        and result["ranking"] >= THRESHOLDS["ranking"]
        and result["unverified"] == THRESHOLDS["unverified"]
        and result["spread"] is not None
        and result["spread"] <= THRESHOLDS["spread"]
        and not any(s is None for s in spreads.values())
        and not result["non_compliant"]
    )
    return result


async def persona_answer(model: ChatModel, card: dict[str, str], persona: str) -> Answer:
    request = ChatRequest(
        instructions=PERSONA_PROMPT.format(traits=TRAITS[persona].format(**card)),
        messages=(ChatMessage("user", card["question"]),),
        temperature=0.7,
        max_output_tokens=400,
        reasoning="off",
    )
    text = ""
    for attempt in range(1, ATTEMPTS + 1):
        text = " ".join((await model.complete(request)).text.split())
        if traits_present(text, card, persona):
            return Answer(card["id"], persona, card["question"], text, True, attempt)
    return Answer(card["id"], persona, card["question"], text, False, ATTEMPTS)


def saved_answers(path: Path, cards: list[dict[str, str]]) -> tuple[list[Answer], str, str]:
    """Reuse the exact generated answers across evaluators, checking their card identity again."""
    record = json.loads(path.read_text(encoding="utf-8"))
    by_id = {card["id"]: card for card in cards}
    answers = [Answer(**item) for item in record["answers"] if item["card"] in by_id]
    expected = {(card, persona) for card in by_id for persona in ("weak", "strong")}
    if len(answers) != len(expected) or {(a.card, a.persona) for a in answers} != expected:
        raise ValueError("saved answers must contain each selected card and persona exactly once")
    if any(a.question != by_id[a.card]["question"] for a in answers):
        raise ValueError("saved answers belong to a different question fixture")
    return (
        [replace(a, compliant=traits_present(a.text, by_id[a.card], a.persona)) for a in answers],
        str(record["persona_model"]),
        str(record.get("persona_prompt_ref", "persona@v1")),
    )


async def checkpoint(path: Path, record: dict[str, Any]) -> None:
    def write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    await asyncio.to_thread(write)


def answers_digest(answers: list[Answer]) -> str:
    rows = sorted((a.card, a.persona, a.question, a.text) for a in answers)
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def checked_audit(path: Path, answers: list[Answer]) -> dict[str, Any]:
    """An audit attests source checking; it cannot itself prove the generated claims true."""
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if record.get("answers_sha256") != answers_digest(answers):
        raise ValueError("answer audit does not match the generated answers")
    checks = record.get("checks", [])
    expected = {(a.card, a.persona) for a in answers}
    if len(checks) != len(expected) or {(c["card"], c["persona"]) for c in checks} != expected:
        raise ValueError("answer audit must cover every selected card and persona exactly once")
    if any(
        c.get("label_verified") is not True or not c.get("notes") or not c.get("sources")
        for c in checks
    ):
        raise ValueError(
            "every answer label needs verified traits, review notes and primary sources"
        )
    return record


async def run(args: argparse.Namespace) -> int:
    settings = Settings()
    cards = json.loads(CARDS.read_text(encoding="utf-8"))
    if args.cards:
        cards = [c for c in cards if c["id"] in set(args.cards)]
    persona_model = OllamaChatModel(
        base_url=settings.ollama_base_url,
        model=args.persona_model or settings.interviewer_model,
        context_window=settings.context_window,
        timeout_s=600,
    )
    if args.answers_from:
        answers, persona_ref, persona_prompt_ref = saved_answers(args.answers_from, cards)
    else:
        # All answers first, so each model is loaded once on a single GPU.
        persona_services = build(settings) if args.persona_profile == "cloud" else None
        generator: ChatModel = (
            persona_services.roles["interviewer"].pinned("cloud")
            if persona_services
            else persona_model
        )
        try:
            answers = []
            for card in cards:
                for persona in ("weak", "strong"):
                    answer = await persona_answer(generator, card, persona)
                    answers.append(answer)
                    print(
                        json.dumps(
                            {
                                "generated": f"{answer.card}/{answer.persona}",
                                "compliant": answer.compliant,
                                "attempts": answer.attempts,
                            }
                        ),
                        flush=True,
                    )
            persona_ref = generator.model_ref
        finally:
            if persona_services:
                await persona_services.shutdown()
        persona_prompt_ref = "persona@v3"
    if args.answers_only:
        await checkpoint(
            args.output,
            {
                "benchmark_ref": BENCHMARK_REF,
                "status": "answers_ready",
                "persona_model": persona_ref,
                "persona_prompt_ref": persona_prompt_ref,
                "answers_sha256": answers_digest(answers),
                "answers": [asdict(a) for a in answers],
            },
        )
        return 0 if all(a.compliant for a in answers) else 1
    full_run = args.regenerations >= 5 and len(cards) == len(json.loads(CARDS.read_text()))
    if full_run and not args.audit:
        raise ValueError(
            "full calibration requires --audit; generate --answers-only for review first"
        )
    audit = checked_audit(args.audit, answers) if args.audit else None
    # Use the application's composition root without starting jobs or migrating its database.
    services = build(settings)
    evaluation_model: ChatModel = services.roles["evaluation"].pinned(args.profile)
    if args.debug_log:
        evaluation_model = DebugLogChatModel(evaluation_model, args.debug_log)
    evaluator = InterviewReviewer(evaluation_model)

    async def quiet(value: float, message: str | None) -> None:
        pass

    assessments: list[Assessment] = []
    reports: list[dict[str, Any]] = []
    record: dict[str, Any] = {
        "benchmark_ref": BENCHMARK_REF,
        "profile": args.profile,
        "status": "running",
        "regenerations_requested": args.regenerations,
        "rubric_ref": evaluator.rubric_ref,
        "prompt_ref": evaluator.prompt_ref,
        "persona_model": persona_ref,
        "persona_prompt_ref": persona_prompt_ref,
        "answers_sha256": answers_digest(answers),
        "input_audit": audit,
        "evaluator": evaluator.model.model_ref,
        "thresholds": THRESHOLDS,
        "summary": None,
        "answers": [asdict(a) for a in answers],
        "reports": reports,
    }
    await checkpoint(args.output, record)
    try:
        for regeneration in range(args.regenerations):
            for answer in answers:
                started = time.monotonic()
                result = await evaluator.review(
                    session_for(answer.question, answer.text), None, "en", quiet
                )
                item = assessment_of(answer, regeneration, result, time.monotonic() - started)
                assessments.append(item)
                reports.append({"assessment": asdict(item), "result": asdict(result)})
                record["summary"] = summary(
                    answers, assessments, {c["id"]: c["wrong_claim"] for c in cards}
                )
                await checkpoint(args.output, record)
                print(json.dumps(asdict(item)), flush=True)
    finally:
        await services.shutdown()
    outcome = record["summary"]
    record["status"] = "completed"
    record["calibration_complete"] = full_run and audit is not None and not outcome["non_compliant"]
    await checkpoint(args.output, record)
    print(json.dumps(outcome, indent=2), flush=True)
    return 0 if outcome["passed"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regenerations", type=int, default=5)
    parser.add_argument("--cards", nargs="*", help="card ids; all cards by default")
    parser.add_argument("--persona-model", default=None, help="defaults to the interviewer model")
    parser.add_argument("--persona-profile", choices=("local", "cloud"), default="local")
    parser.add_argument("--debug-log", type=Path, default=None, help="JSONL of evaluator calls")
    parser.add_argument("--profile", choices=("local", "cloud"), default="local")
    parser.add_argument("--answers-from", type=Path, help="reuse a saved run's generated answers")
    parser.add_argument(
        "--audit", type=Path, help="source-checked labels matching the saved answers"
    )
    parser.add_argument(
        "--answers-only", action="store_true", help="generate answers for audit first"
    )
    args = parser.parse_args()
    if args.regenerations < 1:
        parser.error("--regenerations must be positive")
    if args.persona_profile == "cloud" and args.persona_model:
        parser.error(
            "--persona-model selects a local model; use cloud settings for the cloud profile"
        )
    if args.answers_from and args.answers_from.resolve() == args.output.resolve():
        parser.error("--output must not overwrite --answers-from")
    if args.cards and not set(args.cards) <= {c["id"] for c in json.loads(CARDS.read_text())}:
        parser.error("unknown card id")
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
