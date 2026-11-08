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

False corrections on strong answers, discarded items and criterion coverage are recorded too.
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
import json
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz
from tests.conftest import make_session

from probeloop.ai.debuglog import DebugLogChatModel
from probeloop.ai.ollama import OllamaChatModel
from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest
from probeloop.assessment.application.interview_review import InterviewJudgement, InterviewReviewer
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
_FIRST_PERSON = re.compile(r"\bI\b")
_DIGIT = re.compile(r"\d")

PERSONA_PROMPT = """You play a job candidate in a practice interview for an automated test.
Answer the interviewer's question in English, in 90 to 160 words, as natural spoken text
without lists or headings. Never mention that you are playing a role or that this is a test.
Traits of this answer:
{traits}"""

TRAITS = {
    "weak": (
        "- Include this sentence word for word and present it as a fact: {wrong_claim}\n"
        "- Describe the work only as what 'we' or 'the team' did: no decision of your own, no "
        "constraint, no alternative and no concrete outcome.\n"
        "- Give no numbers, percentages or measurements."
    ),
    "strong": (
        "- Be technically correct and consistent with: {correct_fact}\n"
        "- Describe one specific situation you handled yourself: the constraints, an alternative "
        "you rejected and why, and a concrete outcome."
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
    detected = possible = 0
    for item in weak:
        if (item.card, "weak") not in usable:
            continue
        claim = wrong_claims[item.card]
        flagged = any(
            fuzz.partial_ratio(normalise(q), normalise(claim)) >= 85 for q in item.corrections
        )
        detected += flagged or (item.accuracy is not None and item.accuracy <= 2)
        detected += item.experience is not None and item.experience <= 2
        possible += 2
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
    result = {
        "detection": round(detected / possible, 3) if possible else None,
        "ranking": round(ranked / pairs, 3) if pairs else None,
        "unverified": sum(a.unverified for a in assessments),
        "spread": max((s for s in spreads.values() if s is not None), default=None),
        "spreads": spreads,
        "false_corrections": sum(len(a.corrections) for a in assessments if a.persona == "strong"),
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
    # All answers first, so each model is loaded once on a single GPU.
    answers = [
        await persona_answer(persona_model, card, persona)
        for card in cards
        for persona in ("weak", "strong")
    ]
    evaluation_model: ChatModel = OllamaChatModel(
        base_url=settings.ollama_base_url,
        model=settings.evaluation_model,
        context_window=settings.evaluation_context_window,
        timeout_s=600,
    )
    if args.debug_log:
        evaluation_model = DebugLogChatModel(evaluation_model, args.debug_log)
    evaluator = InterviewReviewer(evaluation_model)

    async def quiet(value: float, message: str | None) -> None:
        pass

    assessments: list[Assessment] = []
    reports: list[dict[str, Any]] = []
    for regeneration in range(args.regenerations):
        for answer in answers:
            started = time.monotonic()
            result = await evaluator.review(
                session_for(answer.question, answer.text), None, "en", quiet
            )
            item = assessment_of(answer, regeneration, result, time.monotonic() - started)
            assessments.append(item)
            reports.append({"assessment": asdict(item), "result": asdict(result)})
            print(json.dumps(asdict(item)), flush=True)
    outcome = summary(answers, assessments, {c["id"]: c["wrong_claim"] for c in cards})
    record = {
        "prompt_ref": evaluator.prompt_ref,
        "persona_model": persona_model.model_ref,
        "evaluator": evaluator.model.model_ref,
        "thresholds": THRESHOLDS,
        "summary": outcome,
        "answers": [asdict(a) for a in answers],
        "reports": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(
        args.output.write_text, json.dumps(record, ensure_ascii=False, indent=2)
    )
    print(json.dumps(outcome, indent=2), flush=True)
    return 0 if outcome["passed"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regenerations", type=int, default=5)
    parser.add_argument("--cards", nargs="*", help="card ids; all cards by default")
    parser.add_argument("--persona-model", default=None, help="defaults to the interviewer model")
    parser.add_argument("--debug-log", type=Path, default=None, help="JSONL of evaluator calls")
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
