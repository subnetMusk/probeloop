"""Build adaptive turn context and validate intent before emitting any question audio."""

import json
import math
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict, replace
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from probeloop.ai.ports import (
    CHARS_PER_TOKEN,
    ChatMessage,
    ChatModel,
    ChatRequest,
    estimated_tokens,
)
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import (
    FieldDelta,
    StructuredOutputError,
    complete_structured,
    stream_structured,
)
from probeloop.context.application.snapshots import select_facts
from probeloop.context.domain.model import Fact, FactOrigin, Subject
from probeloop.interview.application.ports import MoveDelta, MoveDone, MoveRequest
from probeloop.interview.domain.adaptive_policy import MAX_HINTS, topic_windows
from probeloop.interview.domain.model import (
    ASSESSMENT_CRITERIA,
    CandidateTurn,
    InterviewerMove,
    InterviewerTurn,
    MoveAction,
    MovePurpose,
    TurnIntent,
)
from probeloop.interview.domain.time_policy import TimeDirective


class AnswerLimit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["cannot_recall", "no_experience", "needs_clarification"]
    quote: str = Field(min_length=8, max_length=300)


# Objective, criterion and fact identifiers. The bound keeps a decision's size predictable.
Identifier = Annotated[str, Field(max_length=32)]


class AdaptiveChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Flow context only, never a score or a diagnosis of the candidate's abilities.
    answer_limit: AnswerLimit | None = None
    topic_id: Identifier
    purpose: MovePurpose
    past_example: bool
    elicited_criteria: list[Identifier] = Field(max_length=8)
    fact_ids: list[Identifier] = Field(max_length=12)
    covered_topic_ids: list[Identifier] = Field(max_length=32)


class AdaptiveHeader(AdaptiveChoice):
    """Internal header: code derives control fields from the model's decision and history."""

    action: Literal["follow_up", "clarify", "new_topic", "wrap_up", "end"]
    answer_seq: int | None
    hint_level: int = Field(ge=0, le=MAX_HINTS)
    rubric_kind: str | None = None

    def intent(self) -> TurnIntent:
        return TurnIntent(
            self.purpose,
            self.past_example,
            tuple(self.elicited_criteria),
            tuple(self.fact_ids),
            self.answer_seq,
            self.hint_level,
            self.rubric_kind,
            self.answer_limit.kind if self.answer_limit else None,
        )


class AdaptiveMoveOutput(AdaptiveChoice):
    # Essential metadata precedes the streamed field, including coverage.
    utterance: str = Field(min_length=1, max_length=1800)


class AdaptiveDecision(AdaptiveChoice):
    """First step of a two-step turn: the decision, validated before any question text exists."""

    # The single thing the next question will ask, stated before the question is written.
    focus: str = Field(min_length=5, max_length=240)


class QuestionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    utterance: str = Field(min_length=1, max_length=1800)


class StatedLimits(BaseModel):
    """Verbatim statements of what the candidate does not remember or has not experienced."""

    model_config = ConfigDict(extra="forbid")
    quotes: list[Annotated[str, Field(min_length=8, max_length=300)]] = Field(max_length=4)


def checked_header(
    choice: AdaptiveChoice, request: MoveRequest, *, frame_from_objective: bool = True
) -> AdaptiveHeader:
    topic = next((t for t in request.context.topics if t.id == choice.topic_id), None)
    if topic is None:
        raise StructuredOutputError("unknown objective")
    moves = [t for t in request.turns if isinstance(t, InterviewerTurn)]
    answers = [t for t in request.turns if isinstance(t, CandidateTurn)]
    purposes = {
        MovePurpose.NEW_TOPIC: "new_topic",
        MovePurpose.CLARIFICATION: "clarify",
        MovePurpose.EVIDENCE_PROBE: "follow_up",
        MovePurpose.REASONING_PROBE: "follow_up",
        MovePurpose.HINT: "follow_up",
    }
    if choice.purpose is MovePurpose.CLOSING:
        action = (
            "end"
            if (
                request.directive in (TimeDirective.CLOSE, TimeDirective.FORCE_CLOSE)
                or (moves and moves[-1].move.topic_id == topic.id)
            )
            else "wrap_up"
        )
    else:
        action = purposes[choice.purpose]
    hints = sum(
        t.move.topic_id == topic.id
        and t.move.intent is not None
        and t.move.intent.purpose is MovePurpose.HINT
        for t in moves
    )
    if choice.purpose is MovePurpose.HINT and hints >= MAX_HINTS:
        raise StructuredOutputError("at most two hints per objective")
    past = choice.past_example and choice.purpose not in (
        MovePurpose.CLARIFICATION,
        MovePurpose.CLOSING,
    )
    if frame_from_objective and choice.purpose is MovePurpose.NEW_TOPIC:
        # Code will actually speak this objective's evidence frame before the generated question.
        past = topic.past_example
    kind = topic.rubric_kind or "logistics"
    if kind in ("behavioral", "hypothetical") and choice.purpose is not MovePurpose.CLARIFICATION:
        kind = "behavioral" if past else "hypothetical"
    allowed = set(ASSESSMENT_CRITERIA[kind])
    if not past:
        allowed -= {"experience", "ownership", "specificity", "results", "reflection"}
    if past or kind not in ("technical", "hypothetical"):
        allowed.discard("autonomy")
    if not answers:
        allowed.discard("followup_depth")
    if choice.purpose in (MovePurpose.CLARIFICATION, MovePurpose.CLOSING):
        allowed.clear()
    elicited = list(dict.fromkeys(c for c in choice.elicited_criteria if c in allowed))
    task = set(elicited) & {
        "reasoning",
        "problem_solving",
        "tradeoffs",
        "plan",
        "risks",
        "validation",
    }
    if "autonomy" in allowed and "autonomy" not in elicited and task:
        # A declared reasoning task elicits autonomy even if the model omits its id.
        elicited.append("autonomy")
    if "autonomy" in elicited and not task:
        # Autonomy is shown on a reasoning task; without one the question cannot elicit it.
        elicited.remove("autonomy")
    if (
        frame_from_objective
        and past
        and (
            not moves
            or choice.purpose is MovePurpose.NEW_TOPIC
            or (moves[-1].move.intent is not None and not moves[-1].move.intent.past_example)
        )
    ):
        # question_frame actually requests this evidence; it is not inferred from a goal.
        elicited.extend(
            c for c in ("experience", "ownership") if c in allowed and c not in elicited
        )
    answered: set[str] = set()
    current = ""
    for turn in request.turns:
        if isinstance(turn, InterviewerTurn):
            current = turn.move.topic_id
        elif current:
            answered.add(current)
    header = AdaptiveHeader.model_validate(
        {
            **choice.model_dump(),
            "action": action,
            "past_example": past,
            "elicited_criteria": elicited,
            "covered_topic_ids": [i for i in choice.covered_topic_ids if i in answered],
            "answer_seq": answers[-1].seq
            if answers and choice.purpose not in (MovePurpose.NEW_TOPIC, MovePurpose.CLOSING)
            else None,
            "hint_level": hints + 1 if choice.purpose is MovePurpose.HINT else 0,
            "rubric_kind": kind,
        }
    )
    validate_header(header, request)
    return header


def fact_entry(fact: Fact, request: MoveRequest) -> dict[str, object]:
    """A fact as the interviewer sees it: the source's own words unless the user corrected it."""
    return {
        "id": fact.id,
        "subject": fact.subject.value,
        "kind": fact.kind.value,
        "origin": fact.origin.value,
        "document_kind": dict(request.context.document_kinds).get(fact.document_id or ""),
        "text": fact.quote
        if fact.origin is FactOrigin.DECLARED and fact.quote and not fact.corrected
        else fact.text,
        "review": fact.review.value,
    }


def selected_facts(request: MoveRequest, max_chars: int = 3000) -> tuple[Fact, ...]:
    moves = [t for t in request.turns if isinstance(t, InterviewerTurn)]
    topic = next(
        (t for t in request.context.topics if moves and t.id == moves[-1].move.topic_id),
        request.context.topics[0],
    )
    answers = [t for t in request.turns if isinstance(t, CandidateTurn)]
    query = " ".join((topic.title, answers[-1].text if answers else ""))
    return tuple(
        f
        for subject in Subject
        for f in select_facts(
            tuple(f for f in request.context.facts if f.subject is subject and f.asserted),
            query=query,
            preferred_ids=topic.fact_ids,
            max_chars=max_chars,
            measure=lambda fact: len(json.dumps(fact_entry(fact, request), ensure_ascii=False)),
        )
    )


# Prompt reductions tried in order until the request fits the model's context window: first
# fewer whole facts, then earlier turns replaced by a compact record. Persisted data is unchanged.
FIT_PLANS: tuple[tuple[int, int | None], ...] = (
    (3000, None),
    (2000, None),
    (1200, None),
    (1200, 16),
    (1200, 12),
    (1200, 8),
    (600, 6),
    (0, 4),
)
EARLIER_CHARS = 200


def adaptive_request(
    prompts: PromptRenderer,
    request: MoveRequest,
    *,
    language_name: str,
    type_guidance: str,
    difficulty_guidance: str,
    temperature: float,
    top_p: float,
    version: int = 2,
    context_window: int | None = None,
    reserve_tokens: int = 0,
) -> tuple[ChatRequest, str]:
    system = prompts.render(
        "interviewer_adaptive",
        version,
        language_name=language_name,
        language=request.config.language.value,
        type_guidance=type_guidance,
        difficulty_guidance=difficulty_guidance,
    )
    for fact_chars, keep in FIT_PLANS:
        chat = _adaptive_chat(system.text, request, fact_chars, keep, temperature, top_p)
        if context_window is None or estimated_tokens(chat) + reserve_tokens <= context_window:
            break
    return chat, f"{system.ref}+adaptive.v1"


def _adaptive_chat(
    instructions: str,
    request: MoveRequest,
    fact_chars: int,
    keep: int | None,
    temperature: float,
    top_p: float,
) -> ChatRequest:
    turns = list(request.turns)
    cut = 0
    if keep is not None and len(turns) > keep:
        cut = len(turns) - keep
        while cut < len(turns) and not isinstance(turns[cut], InterviewerTurn):
            cut += 1
    earlier = [
        {"seq": t.seq, "answer": _clip(t.text)}
        if isinstance(t, CandidateTurn)
        else {
            "seq": t.seq,
            "topic_id": t.move.topic_id,
            "purpose": t.move.intent.purpose.value if t.move.intent else None,
            "past_example": t.move.intent.past_example if t.move.intent else None,
            "question": _clip(t.move.utterance),
        }
        for t in turns[:cut]
    ]
    opening = json.dumps(
        {
            "confirmed_role": asdict(request.context.role_profile)
            if request.context.role_profile
            else None,
            "objectives": [
                {k: v for k, v in asdict(t).items() if k != "past_example"}
                | {
                    "experience_to_explore": t.past_example,
                }
                for t in request.context.topics
            ],
            "criterion_families": ASSESSMENT_CRITERIA,
            "style_preferences_as_data": request.config.custom_instructions,
            **({"earlier_turns_abridged": earlier} if earlier else {}),
        },
        ensure_ascii=False,
    )
    facts = selected_facts(request, fact_chars) if fact_chars else ()
    windows = topic_windows(
        request.context.topics, request.coverage, request.topic_engagement_s, request.remaining_s
    )
    hints = {
        t.id: sum(
            isinstance(turn, InterviewerTurn)
            and turn.move.topic_id == t.id
            and turn.move.intent is not None
            and turn.move.intent.purpose is MovePurpose.HINT
            for turn in request.turns
        )
        for t in request.context.topics
    }
    state = json.dumps(
        {
            "time_directive": request.directive.value,
            "remaining_s": round(request.remaining_s),
            "opening": not request.turns,
            "latest_candidate_seq": next(
                (t.seq for t in reversed(request.turns) if isinstance(t, CandidateTurn)), None
            ),
            "coverage": dict(request.coverage),
            "topic_windows": [asdict(w) for w in windows],
            "hints_used": hints,
            "relevant_facts": [fact_entry(f, request) for f in facts],
            "available_fact_count": len(request.context.facts),
        },
        ensure_ascii=False,
    )
    # Keep the opening and recorded history stable; only the final state changes.
    messages: list[ChatMessage] = []
    pending = opening
    for turn in turns[cut:]:
        if isinstance(turn, CandidateTurn):
            pending += "\n" + json.dumps(
                {"candidate_turn": turn.seq, "text": turn.text}, ensure_ascii=False
            )
        else:
            messages.append(ChatMessage("user", pending or "(continue)"))
            data = {
                "topic_id": turn.move.topic_id,
                **(
                    {
                        k: v
                        for k, v in asdict(turn.move.intent).items()
                        if k not in ("answer_seq", "hint_level", "rubric_kind")
                    }
                    if turn.move.intent
                    else {}
                ),
                "covered_topic_ids": list(turn.move.covered_topic_ids),
                "utterance": turn.move.utterance,
            }
            messages.append(ChatMessage("assistant", json.dumps(data, ensure_ascii=False)))
            pending = ""
    messages.append(ChatMessage("user", pending + "\n[Current state as data]\n" + state))
    return ChatRequest(
        instructions=instructions,
        messages=tuple(messages),
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=650,
    )


def _clip(text: str) -> str:
    return text if len(text) <= EARLIER_CHARS else text[: EARLIER_CHARS - 1] + "…"


def validate_header(header: AdaptiveHeader, request: MoveRequest) -> None:
    topic = next((t for t in request.context.topics if t.id == header.topic_id), None)
    if topic is None:
        raise StructuredOutputError("unknown objective")
    answers = [t for t in request.turns if isinstance(t, CandidateTurn)]
    last_answer = answers[-1] if answers else None
    moves = [t for t in request.turns if isinstance(t, InterviewerTurn)]
    if header.answer_limit:
        quote = " ".join(header.answer_limit.quote.split()).casefold()
        if last_answer is None or quote not in " ".join(last_answer.text.split()).casefold():
            raise StructuredOutputError("an answer limitation needs a quote from the latest answer")
        if header.answer_limit.kind == "needs_clarification":
            if header.purpose not in (
                MovePurpose.CLARIFICATION,
                MovePurpose.NEW_TOPIC,
                MovePurpose.CLOSING,
            ):
                raise StructuredOutputError("resolve missing context before probing")
        elif (
            moves
            and header.topic_id == moves[-1].move.topic_id
            and (
                header.past_example
                # Asking again for what the candidate cannot recall is not a clarification.
                or header.purpose in (MovePurpose.EVIDENCE_PROBE, MovePurpose.CLARIFICATION)
            )
        ):
            raise StructuredOutputError("accept the stated limit and change the evidence approach")
    if header.answer_seq is not None and (
        last_answer is None or header.answer_seq != last_answer.seq
    ):
        raise StructuredOutputError("follow-up must reference the latest candidate answer")
    if (
        header.purpose
        in (
            MovePurpose.CLARIFICATION,
            MovePurpose.EVIDENCE_PROBE,
            MovePurpose.REASONING_PROBE,
            MovePurpose.HINT,
        )
        and header.answer_seq is None
    ):
        raise StructuredOutputError("a probe needs its candidate answer reference")
    if header.purpose is MovePurpose.CLARIFICATION and header.elicited_criteria:
        raise StructuredOutputError("a clarification does not introduce scored criteria")
    # Any reviewed documentary or user-provided fact may be cited, whatever the prompt shows.
    verified = {f.id for f in request.context.facts if f.asserted}
    if not set(header.fact_ids) <= verified:
        raise StructuredOutputError("unavailable documentary reference")
    answered_topics: set[str] = set()
    current = ""
    for turn in request.turns:
        if isinstance(turn, InterviewerTurn):
            current = turn.move.topic_id
        elif current:
            answered_topics.add(current)
    if not set(header.covered_topic_ids) <= answered_topics:
        raise StructuredOutputError("unanswered objectives cannot be marked covered")
    closing = topic.rubric_kind == "logistics"
    if (
        request.directive
        in (
            TimeDirective.FINAL_QUESTION,
            TimeDirective.CLOSE,
            TimeDirective.FORCE_CLOSE,
        )
        and not closing
    ):
        raise StructuredOutputError("global closing takes precedence")
    windows = topic_windows(
        request.context.topics, request.coverage, request.topic_engagement_s, request.remaining_s
    )
    if closing:
        if (
            header.purpose is not MovePurpose.CLOSING
            or header.elicited_criteria
            or header.hint_level
        ):
            raise StructuredOutputError("closing is not an assessment or a hint")
        # A closing already started, including a fixed fallback one, can only end.
        started = bool(moves) and moves[-1].move.topic_id == topic.id
        if (
            request.directive is TimeDirective.NORMAL
            and not started
            and any(w.available for w in windows)
        ):
            raise StructuredOutputError("objectives with time left precede the closing")
        expected = (
            "end"
            if started or request.directive in (TimeDirective.CLOSE, TimeDirective.FORCE_CLOSE)
            else "wrap_up"
        )
        if header.action != expected:
            raise StructuredOutputError("invalid closing action")
        return
    if header.action in ("wrap_up", "end") or header.purpose is MovePurpose.CLOSING:
        raise StructuredOutputError("closing needs its closing objective")
    if request.directive is TimeDirective.BEGIN_WRAP_UP and (
        not moves
        or header.topic_id != moves[-1].move.topic_id
        or any(t.elapsed_s >= request.config.target_duration_s * 0.85 for t in moves)
    ):
        raise StructuredOutputError("wrap-up permits at most one final current-topic probe")
    if not next(w.available for w in windows if w.topic_id == topic.id):
        raise StructuredOutputError("move on from an exhausted or covered objective")
    if header.action == "new_topic" and header.purpose is not MovePurpose.NEW_TOPIC:
        raise StructuredOutputError("a topic change must be explicit")
    if moves and header.topic_id != moves[-1].move.topic_id and header.action != "new_topic":
        raise StructuredOutputError("a different objective requires a topic change")
    if not set(header.elicited_criteria) <= set(
        ASSESSMENT_CRITERIA[header.rubric_kind or topic.rubric_kind or "logistics"]
    ):
        raise StructuredOutputError("question criteria do not belong to the objective's rubric")
    if not header.past_example and set(header.elicited_criteria) & {
        "experience",
        "ownership",
        "specificity",
        "results",
        "reflection",
    }:
        raise StructuredOutputError("a plan does not elicit first-hand experience or outcomes")
    if "followup_depth" in header.elicited_criteria and not last_answer:
        raise StructuredOutputError("follow-up depth requires a prior answer")
    if "autonomy" in header.elicited_criteria and (
        header.past_example
        or not set(header.elicited_criteria)
        & {"reasoning", "problem_solving", "tradeoffs", "plan", "risks", "validation"}
    ):
        raise StructuredOutputError("autonomy needs an elicited role-relevant reasoning task")
    if header.purpose is MovePurpose.HINT:
        previous = next((t.move for t in reversed(moves) if t.move.topic_id == topic.id), None)
        count = sum(
            t.move.intent is not None and t.move.intent.purpose is MovePurpose.HINT
            for t in moves
            if t.move.topic_id == topic.id
        )
        if (
            not topic.solvable
            or header.past_example
            or previous is None
            or previous.intent is None
            or previous.intent.past_example
            or count >= MAX_HINTS
            or header.hint_level != count + 1
        ):
            raise StructuredOutputError(
                "hints require an existing solvable task and at most two steps"
            )
    elif header.hint_level:
        raise StructuredOutputError("only an actual hint can record a hint level")


async def stream_adaptive_move(
    model: ChatModel,
    chat_request: ChatRequest,
    request: MoveRequest,
    prompt_ref: str,
) -> AsyncIterator[MoveDelta | MoveDone]:
    header: AdaptiveHeader | None = None
    buffered = ""
    spoken = ""
    async for item in stream_structured(
        model, chat_request, AdaptiveMoveOutput, stream_field="utterance"
    ):
        if isinstance(item, FieldDelta):
            buffered += item.text
            if header is None:
                if any(key not in item.partial for key in AdaptiveChoice.model_fields):
                    continue
                try:
                    choice = AdaptiveChoice.model_validate(
                        {k: v for k, v in item.partial.items() if k in AdaptiveChoice.model_fields}
                    )
                except ValidationError:
                    # Providers may order JSON differently; wait for complete metadata.
                    continue
                header = checked_header(choice, request)
            text = _speakable(buffered, header.action, spoken)
            buffered = ""
            if text:
                if not spoken:
                    text = question_frame(request, header) + text
                spoken += text
                yield MoveDelta(text, MoveAction(header.action), header.topic_id, header.intent())
        else:
            final = checked_header(
                AdaptiveChoice.model_validate(item.value.model_dump(exclude={"utterance"})), request
            )
            if header is not None and header != final:
                raise StructuredOutputError("essential question metadata changed after emission")
            utterance = (
                question_frame(request, final)
                + _speakable(item.value.utterance, final.action, "").strip()
            )
            if not spoken:
                yield MoveDelta(utterance, MoveAction(final.action), final.topic_id, final.intent())
            yield MoveDone(
                InterviewerMove(
                    MoveAction(final.action),
                    final.topic_id,
                    utterance,
                    tuple(final.covered_topic_ids),
                    model_ref=model.model_ref,
                    prompt_ref=prompt_ref,
                    intent=final.intent(),
                )
            )


DECIDE = (
    "\n[Step 1: decide] Return only the decision for the next move: its metadata and a focus "
    "sentence naming the single thing the question will ask and whether it concerns the "
    "candidate's actual past or a hypothetical situation. Do not write the question yet."
)


def _normalised(text: str) -> str:
    return " ".join(text.split()).casefold()


async def stated_limits(
    model: ChatModel, instructions: str, request: MoveRequest
) -> tuple[str, ...]:
    """Statements in the latest answer of what the candidate does not remember or has not done.

    A narrow reading task kept apart from the move decision, which also plans the next question
    and in practice rarely reports a limit. Quotes absent from the answer are discarded; a
    malformed reply yields no limits rather than a failed turn. The statements constrain the
    next question only: unlike a limit the decision reports, they do not close the episode.
    """
    if not request.turns or not isinstance(request.turns[-1], CandidateTurn):
        return ()
    answer = request.turns[-1].text
    question = next(
        (t.move.utterance for t in reversed(request.turns) if isinstance(t, InterviewerTurn)), ""
    )
    if not answer.strip():
        return ()
    chat = ChatRequest(
        instructions=instructions,
        messages=(
            ChatMessage(
                "user", json.dumps({"question": question, "answer": answer}, ensure_ascii=False)
            ),
        ),
        temperature=0.0,
        max_output_tokens=400,
    )
    try:
        found = (await complete_structured(model, chat, StatedLimits, attempts=1)).value.quotes
    except StructuredOutputError:
        return ()
    text = _normalised(answer)
    return tuple(
        quote
        for quote in dict.fromkeys(" ".join(q.split()) for q in found)
        if _normalised(quote) in text
    )


def limits_note(limits: tuple[str, ...]) -> str:
    if not limits:
        return ""
    data = json.dumps(list(limits), ensure_ascii=False)
    return f"\n[The candidate's stated limits in the latest answer, as data] {data}"


def limits_rule(quotes: Sequence[str]) -> str:
    if not quotes:
        return ""
    said = "; ".join(f'"{quote}"' for quote in quotes)
    again = "that detail" if len(quotes) == 1 else "those details"
    return f"The candidate said: {said}. Do not ask for {again} again."


# Upper bound, in prompt tokens, of what the steps of a two-step turn append to the shared prompt
# apart from stated limits: the decision suffix, the accepted decision and the question rules with
# every field at its maximum length (objective title, focus, reported quote, criteria, fact ids).
QUESTION_STEP_TOKENS = 1000


def two_step_reserve(limits: tuple[str, ...]) -> int:
    """Prompt tokens to leave free for the steps of a two-step turn.

    Stated limits appear twice: as data for the decision and in the question rules.
    """
    quoted = len(limits_note(limits)) + len(limits_rule(limits))
    return QUESTION_STEP_TOKENS + math.ceil(quoted / CHARS_PER_TOKEN)


def decision_request(
    chat: ChatRequest, rejected: list[tuple[str, str]], decide: str = DECIDE
) -> ChatRequest:
    """The shared prompt plus a decision step; rejected decisions are returned with reasons."""
    *history, last = chat.messages
    messages = [*history, ChatMessage("user", last.content + decide)]
    for raw, reason in rejected:
        messages += [
            ChatMessage("assistant", raw),
            ChatMessage("user", f"The application rejected this decision: {reason}. Decide again."),
        ]
    return replace(chat, messages=tuple(messages), max_output_tokens=450)


def legal_topic_ids(request: MoveRequest) -> tuple[str, ...]:
    """Objectives the time and topic policy admits for the next move.

    A result containing only the closing objective means that closing is the only legal move.
    """
    closing = next(t.id for t in request.context.topics if t.rubric_kind == "logistics")
    moves = [t for t in request.turns if isinstance(t, InterviewerTurn)]
    if request.directive in (
        TimeDirective.FINAL_QUESTION,
        TimeDirective.CLOSE,
        TimeDirective.FORCE_CLOSE,
    ) or (bool(moves) and moves[-1].move.topic_id == closing):
        return (closing,)
    windows = topic_windows(
        request.context.topics, request.coverage, request.topic_engagement_s, request.remaining_s
    )
    available = tuple(w.topic_id for w in windows if w.available)
    if request.directive is TimeDirective.BEGIN_WRAP_UP:
        current = moves[-1].move.topic_id if moves else ""
        final_probe = any(t.elapsed_s >= request.config.target_duration_s * 0.85 for t in moves)
        return (current, closing) if current in available and not final_probe else (closing,)
    return available or (closing,)


def closing_only(request: MoveRequest) -> bool:
    """Whether the time and topic policy leaves closing as the only legal move."""
    closing = next(t.id for t in request.context.topics if t.rubric_kind == "logistics")
    return legal_topic_ids(request) == (closing,)


def decision_output(topic_ids: tuple[str, ...], closing: str) -> type[AdaptiveDecision]:
    """Constrain decoding to the legal objectives and purposes; validation still checks them.

    The closing purpose is offered only while the closing objective is legal.
    """
    purposes = [
        p.value for p in MovePurpose if p is not MovePurpose.CLOSING or closing in topic_ids
    ]

    def legal_purposes(schema: dict[str, Any]) -> None:
        # Inline, not beside the enum's `$ref`: grammar converters may ignore `$ref` siblings.
        schema.clear()
        schema.update({"type": "string", "enum": purposes})

    return create_model(
        "AdaptiveDecision",
        __base__=AdaptiveDecision,
        topic_id=(str, Field(max_length=32, json_schema_extra={"enum": list(topic_ids)})),
        purpose=(MovePurpose, Field(json_schema_extra=legal_purposes)),
    )


def coerced(decision: AdaptiveDecision, request: MoveRequest) -> AdaptiveDecision:
    """Repair purpose/objective contradictions that have only one reading.

    No question text exists yet, so the question step implements the repaired decision. The
    closing objective admits only the closing purpose; a probe of the latest answer under a
    different objective introduces that objective.
    """
    topic = next((t for t in request.context.topics if t.id == decision.topic_id), None)
    moves = [t for t in request.turns if isinstance(t, InterviewerTurn)]
    current = moves[-1].move.topic_id if moves else None
    if topic is not None and topic.rubric_kind == "logistics":
        return decision.model_copy(
            update={
                "purpose": MovePurpose.CLOSING,
                "past_example": False,
                "elicited_criteria": [],
                "fact_ids": [],
            }
        )
    if decision.topic_id != current and decision.purpose in (
        MovePurpose.EVIDENCE_PROBE,
        MovePurpose.REASONING_PROBE,
    ):
        return decision.model_copy(update={"purpose": MovePurpose.NEW_TOPIC})
    return decision


def closing_decision(request: MoveRequest, closing: str) -> AdaptiveDecision:
    moves = [t for t in request.turns if isinstance(t, InterviewerTurn)]
    ending = (bool(moves) and moves[-1].move.topic_id == closing) or request.directive in (
        TimeDirective.CLOSE,
        TimeDirective.FORCE_CLOSE,
    )
    return AdaptiveDecision(
        topic_id=closing,
        purpose=MovePurpose.CLOSING,
        past_example=False,
        elicited_criteria=[],
        fact_ids=[],
        covered_topic_ids=[],
        focus="Say goodbye after any reply to the candidate's questions."
        if ending
        else "Invite the candidate's questions about the role.",
    )


def question_rules(
    request: MoveRequest,
    header: AdaptiveHeader,
    focus: str,
    limits: tuple[str, ...] = (),
) -> str:
    """Code-selected constraints that make the written question implement the decision."""
    topic = next(t for t in request.context.topics if t.id == header.topic_id)
    if header.purpose is MovePurpose.CLOSING and header.action == "end":
        frame = (
            "Answer the candidate's questions only with information in the supplied documents; "
            "otherwise say that it is not available in this practice interview. Then say "
            "goodbye, asking nothing further."
        )
    elif header.purpose is MovePurpose.CLOSING:
        frame = "Ask whether the candidate has questions; ask for no evidence and give no hint."
    elif header.purpose is MovePurpose.CLARIFICATION:
        frame = "Resolve the ambiguity or answer the candidate's question; ask for no new evidence."
    elif header.purpose is MovePurpose.HINT:
        frame = (
            "Give one partial cue for the task already posed, never the solution or a past "
            "experience, then ask the candidate to continue."
        )
    elif header.past_example:
        frame = (
            "Ask only about the candidate's actual past experience. Do not presuppose an event "
            "that neither the answers nor the cited facts contain."
        )
    else:
        frame = (
            "Ask about a hypothetical or general situation, not the candidate's past; state every "
            "scenario detail explicitly as an assumption."
        )
    rules = [f"Objective: {topic.title}.", f"Focus: {focus}", frame]
    limit = header.answer_limit
    quotes = list(
        dict.fromkeys(
            ([limit.quote] if limit and limit.kind != "needs_clarification" else []) + list(limits)
        )
    )
    if quotes:
        rules.append(limits_rule(quotes))
    return (
        "\n[Step 2: ask] The application accepted the decision above. Write only the spoken "
        "question that implements it, without greeting, praise or agreement with the candidate's "
        "claims. " + " ".join(rules)
    )


def opening_greeting(request: MoveRequest) -> str:
    if any(isinstance(t, InterviewerTurn) for t in request.turns):
        return ""
    return "Buongiorno. " if request.config.language.value == "it" else "Hello. "


async def stream_two_step_move(
    model: ChatModel,
    chat_request: ChatRequest,
    request: MoveRequest,
    prompt_ref: str,
    limits: tuple[str, ...] = (),
) -> AsyncIterator[MoveDelta | MoveDone]:
    """Decide and validate first, then write the question that implements the decision.

    When the policy leaves closing as the only legal move, code makes that decision and the
    model writes only the closing words. Limits stated in the latest answer (see stated_limits)
    are supplied to both steps as data; the shared prompt must leave two_step_reserve(limits)
    tokens free.
    """
    rejected: list[tuple[str, str]] = []
    header: AdaptiveHeader | None = None
    decision: AdaptiveDecision | None = None
    legal = legal_topic_ids(request)
    closing = next(t.id for t in request.context.topics if t.rubric_kind == "logistics")
    decide = limits_note(limits) + DECIDE
    for _ in range(2):
        if legal == (closing,):
            decision, raw = closing_decision(request, closing), ""
        else:
            result = await complete_structured(
                model,
                decision_request(chat_request, rejected, decide),
                decision_output(legal, closing),
            )
            decision, raw = coerced(result.value, request), result.raw
        try:
            header = checked_header(
                AdaptiveChoice.model_validate(decision.model_dump(exclude={"focus"})),
                request,
                frame_from_objective=False,
            )
            break
        except StructuredOutputError as exc:
            if not raw:
                raise
            rejected.append((raw, str(exc)))
    if header is None or decision is None:
        raise StructuredOutputError(f"decision rejected: {rejected[-1][1]}")
    *history, last = chat_request.messages
    accepted = json.dumps(
        {k: v for k, v in decision.model_dump(mode="json").items() if k != "covered_topic_ids"},
        ensure_ascii=False,
    )
    question = replace(
        chat_request,
        messages=(
            *history,
            ChatMessage("user", last.content + decide),
            ChatMessage("assistant", accepted),
            ChatMessage("user", question_rules(request, header, decision.focus, limits)),
        ),
    )
    # A decision made by code is not a model label, so only a generated focus is recorded.
    intent = replace(header.intent(), focus=decision.focus if raw else None)
    if intent.answer_limit is None and limits:
        intent = replace(intent, answer_limit="stated_limit")
    spoken = ""
    async for item in stream_structured(model, question, QuestionOut, stream_field="utterance"):
        if isinstance(item, FieldDelta):
            text = _speakable(item.text, header.action, spoken)
            if text:
                if not spoken:
                    text = opening_greeting(request) + text
                spoken += text
                yield MoveDelta(text, MoveAction(header.action), header.topic_id, intent)
        else:
            utterance = (
                opening_greeting(request)
                + _speakable(item.value.utterance, header.action, "").strip()
            )
            action = MoveAction(header.action)
            if not spoken:
                yield MoveDelta(utterance, action, header.topic_id, intent)
            yield MoveDone(
                InterviewerMove(
                    action,
                    header.topic_id,
                    utterance,
                    tuple(header.covered_topic_ids),
                    model_ref=model.model_ref,
                    prompt_ref=prompt_ref.replace("+adaptive.v1", "+adaptive.two_step.v1"),
                    intent=intent,
                )
            )


def question_frame(request: MoveRequest, header: AdaptiveHeader) -> str:
    """An explicit evidence contract, not an assertion that the candidate has that experience."""
    if header.purpose in (MovePurpose.CLOSING, MovePurpose.CLARIFICATION, MovePurpose.HINT):
        return ""
    previous = next((t for t in reversed(request.turns) if isinstance(t, InterviewerTurn)), None)
    changed = (
        previous is None
        or header.action == "new_topic"
        or (
            previous.move.intent is not None
            and previous.move.intent.past_example != header.past_example
        )
    )
    if not changed:
        return ""
    italian = request.config.language.value == "it"
    opening = ("Buongiorno. " if italian else "Hello. ") if previous is None else ""
    if header.past_example:
        return opening + (
            "Usi un esempio reale e descriva il Suo contributo personale; "
            "se non ne dispone, lo dica. "
            if italian
            else "Use a real example and describe your own contribution; say if none applies. "
        )
    if header.rubric_kind in ("technical", "hypothetical"):
        return opening + (
            "Consideriamo uno scenario ipotetico. "
            if italian
            else "Let's use a hypothetical scenario. "
        )
    return opening


def _speakable(text: str, action: str, spoken: str) -> str:
    text = text.replace("*", "")
    if action == "end":
        return text
    if "?" in spoken:
        return ""
    cut = text.find("?")
    return text if cut < 0 else text[: cut + 1]
