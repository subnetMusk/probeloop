"""The LLM-backed interviewer: builds an append-only prompt and streams one move."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest, estimated_tokens
from probeloop.ai.prompts import PromptRenderer
from probeloop.ai.structured import FieldDelta, stream_structured
from probeloop.interview.application.adaptive_interviewer import (
    RECONSTRUCTION_REF,
    RECONSTRUCTION_RESERVE,
    RECONSTRUCTION_TOKENS,
    AdaptiveDecision,
    AdaptiveMoveOutput,
    adaptive_request,
    closing_only,
    single_reserve,
    stream_adaptive_move,
    stream_two_step_move,
    two_step_reserve,
)
from probeloop.interview.application.limits import LlmStatedLimitReader, grounded_quotes
from probeloop.interview.application.ports import (
    MoveDelta,
    MoveDone,
    MoveRequest,
    StatedLimitReader,
)
from probeloop.interview.domain.model import (
    CandidateTurn,
    Difficulty,
    InterviewerMove,
    InterviewerTurn,
    InterviewType,
    Language,
    Modality,
    MoveAction,
    TopicCoverage,
)

# Template versions. Version 2 of the system and state templates followed the M2 persona
# evaluation: compound questions, markdown emphasis and invented names were frequent with v1.
SYSTEM_PROMPT_VERSION = 2
CONTEXT_PROMPT_VERSION = 2  # 2: the vocabulary of technical terms from the documents
STATE_PROMPT_VERSION = 2
LIMITS_PROMPT_VERSION = 1  # adaptive turns: limits stated in the latest answer

LANGUAGE_NAMES = {Language.ITALIAN: "Italian", Language.ENGLISH: "English"}

TYPE_LABELS = {
    InterviewType.HR: "HR (screening)",
    InterviewType.BEHAVIORAL: "behavioural",
    InterviewType.TECHNICAL: "technical",
    InterviewType.MIXED: "mixed",
}

TYPE_GUIDANCE = {
    InterviewType.HR: "motivation, fit with the role, career path and expectations.",
    InterviewType.BEHAVIORAL: (
        "concrete past situations; probe for the candidate's own actions and their results."
    ),
    InterviewType.TECHNICAL: "technical knowledge, reasoning, design choices and trade-offs.",
    InterviewType.MIXED: "a balance of motivational, behavioural and technical questions.",
}

DIFFICULTY_GUIDANCE = {
    Difficulty.EASY: "ask accessible questions and leave the candidate room to elaborate.",
    Difficulty.MEDIUM: "ask questions at the level expected for the role and probe for details.",
    Difficulty.HARD: (
        "probe deeply, ask about trade-offs and edge cases, and challenge vague claims with "
        "precise follow-up questions."
    ),
}


class MoveOutput(BaseModel):
    """The JSON object the model must produce. Field order matters: see ADR 0011."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["follow_up", "clarify", "new_topic", "wrap_up", "end"]
    topic_id: str = Field(max_length=32)
    utterance: str = Field(min_length=1, max_length=1500)
    covered_topic_ids: list[str] = Field(max_length=32)


class LlmInterviewer:
    def __init__(
        self,
        model: ChatModel,
        *,
        temperature: float = 0.6,
        top_p: float = 0.9,
        max_output_tokens: int = 320,
        two_step: bool = False,
        limit_reader: StatedLimitReader | None = None,
        reconstruct_answers: bool = False,
    ) -> None:
        self._model = model
        # Adaptive sessions only: decide and validate, then write the question (two calls).
        # Otherwise one constrained call decides and asks (stream_adaptive_move).
        self._two_step = two_step
        # Adaptive voice sessions only: the move also returns its reading of the latest answer.
        self._reconstruct = reconstruct_answers
        self._limit_reader = limit_reader or LlmStatedLimitReader(model)
        self._prompts = PromptRenderer("probeloop.interview")
        self._temperature = temperature
        self._top_p = top_p
        self._max_output_tokens = max_output_tokens

    async def check(self) -> None:
        await self._model.capabilities()
        # Adaptive turns read stated limits in both turn modes.
        await self._limit_reader.check()

    async def prepare(self, request: MoveRequest) -> None:
        """Send the opening prompt for a single token: loads the model and fills its KV cache.

        A hosted model gains nothing from this; asking for its capabilities still checks that it
        can be used (for example that the user is signed in).
        """
        capabilities = await self._model.capabilities()
        if not capabilities.preload:
            return
        chat_request, _ = self.build_request(request, capabilities.context_window)
        await self._model.complete(
            replace(
                chat_request,
                max_output_tokens=1,
                response_schema=(
                    (AdaptiveDecision if self._two_step else AdaptiveMoveOutput)
                    if request.context.policy_version
                    else MoveOutput
                ).model_json_schema(),
            )
        )

    async def prepare_limits(self) -> None:
        await self._limit_reader.check()

    async def next_move(self, request: MoveRequest) -> AsyncIterator[MoveDelta | MoveDone]:
        """Stream one move. Except in the farewell, the utterance stops at its first question.

        Small models tend to append sub-questions ("Per esempio...?") despite the rules; cutting
        the stream at the first question mark keeps one question per turn and stops the extra
        text from ever reaching the client or the speech synthesiser.
        """
        window = (
            (await self._model.capabilities()).context_window
            if request.context.policy_version
            else None
        )
        if request.context.policy_version:
            # Limits are read first: their quotes enlarge the turn's prompt, so the shared
            # prompt is fitted to the window only once they are known.
            limits: tuple[str, ...] = ()
            limits_ref = ""
            if (
                not closing_only(request)
                and request.turns
                and isinstance(request.turns[-1], CandidateTurn)
                and request.turns[-1].text.strip()
            ):
                answer = request.turns[-1].text
                question = next(
                    (
                        t.move.utterance
                        for t in reversed(request.turns)
                        if isinstance(t, InterviewerTurn)
                    ),
                    "",
                )
                reading = await self._limit_reader.read(question, answer)
                limits = grounded_quotes(answer, reading.quotes)
                limits_ref = f"+{reading.source_ref}"
            wanted = reconstruct = self._reconstruct and self._reconstructs(request)
            chat_request, prompt_ref = self.build_request(
                request, window, limits, reconstruct=reconstruct
            )
            if reconstruct and not self._fits(chat_request, limits, window):
                # A small context window cannot hold the reading as well; the move goes ahead
                # without it and the live transcript stays current.
                reconstruct = False
                chat_request, prompt_ref = self.build_request(request, window, limits)
            stream = stream_two_step_move if self._two_step else stream_adaptive_move
            async for event in stream(
                self._model,
                chat_request,
                request,
                prompt_ref + limits_ref,
                limits,
                reconstruct=reconstruct,
            ):
                if isinstance(event, MoveDone) and wanted and event.answer_transcript is None:
                    # Skipped for the window, rejected as implausible, or not written.
                    event = replace(event, reading_missing=True)
                yield event
            return
        chat_request, prompt_ref = self.build_request(request, window)
        spoken = ""
        async for item in stream_structured(
            self._model, chat_request, MoveOutput, stream_field="utterance"
        ):
            if isinstance(item, FieldDelta):
                action = _action(item.partial.get("action"))
                if action is not MoveAction.END and "?" in spoken:
                    continue
                text = _spoken(item.text)
                if action is not MoveAction.END:
                    text = _first_question(text)
                if text:
                    spoken += text
                    yield MoveDelta(
                        text=text, action=action, topic_id=_str(item.partial.get("topic_id"))
                    )
            else:
                out = item.value
                utterance = _spoken(out.utterance)
                if out.action != MoveAction.END.value:
                    utterance = _first_question(utterance)
                yield MoveDone(
                    InterviewerMove(
                        action=MoveAction(out.action),
                        topic_id=out.topic_id,
                        utterance=utterance.strip(),
                        covered_topic_ids=tuple(out.covered_topic_ids),
                        model_ref=self._model.model_ref,
                        prompt_ref=prompt_ref,
                    )
                )

    def _fits(self, chat: ChatRequest, limits: tuple[str, ...], window: int | None) -> bool:
        """Whether a reconstructing turn, its output included, fits the context window."""
        if window is None:
            return True
        steps = (two_step_reserve if self._two_step else single_reserve)(limits)
        instruction = RECONSTRUCTION_RESERVE - RECONSTRUCTION_TOKENS
        return estimated_tokens(chat) + steps + instruction <= window

    @staticmethod
    def _reconstructs(request: MoveRequest) -> bool:
        """A spoken answer is waiting for its reply; typed answers need no reading."""
        latest = request.turns[-1] if request.turns else None
        return (
            request.config.modality is Modality.VOICE
            and isinstance(latest, CandidateTurn)
            and bool(latest.text.strip())
        )

    def build_request(
        self,
        request: MoveRequest,
        context_window: int | None = None,
        limits: tuple[str, ...] = (),
        *,
        reconstruct: bool = False,
    ) -> tuple[ChatRequest, str]:
        """Build an append-only prompt: everything except the last message is stable.

        With a context window, an adaptive prompt is reduced until it fits (see FIT_PLANS),
        leaving room for both steps of a two-step turn, the stated limits they carry and, with
        `reconstruct`, the reading of the latest answer written after the question.
        """
        config, context = request.config, request.context
        if context.policy_version:
            reserve = (two_step_reserve if self._two_step else single_reserve)(limits)
            chat, ref = adaptive_request(
                self._prompts,
                request,
                language_name=LANGUAGE_NAMES[config.language],
                type_guidance=TYPE_GUIDANCE[config.interview_type],
                difficulty_guidance=DIFFICULTY_GUIDANCE[config.difficulty],
                temperature=self._temperature,
                top_p=self._top_p,
                version=3 if self._two_step else 2,
                context_window=context_window,
                reserve_tokens=reserve + (RECONSTRUCTION_RESERVE if reconstruct else 0),
            )
            if reconstruct:
                chat = replace(
                    chat, max_output_tokens=(chat.max_output_tokens or 0) + RECONSTRUCTION_TOKENS
                )
                ref += f"+{RECONSTRUCTION_REF}"
            return chat, ref
        system = self._prompts.render(
            "interviewer_system",
            SYSTEM_PROMPT_VERSION,
            language=config.language.value,
            language_name=LANGUAGE_NAMES[config.language],
            interview_type_label=TYPE_LABELS[config.interview_type],
            interview_type_guidance=TYPE_GUIDANCE[config.interview_type],
            difficulty_guidance=DIFFICULTY_GUIDANCE[config.difficulty],
        )
        opening = self._prompts.render(
            "interviewer_context",
            CONTEXT_PROMPT_VERSION,
            job_brief=context.job_brief,
            candidate_brief=context.candidate_brief,
            topics=context.topics,
            vocabulary=", ".join(context.vocabulary),
            custom_instructions=config.custom_instructions.strip(),
        )
        state = self._prompts.render(
            "interviewer_state",
            STATE_PROMPT_VERSION,
            covered=_topics_with(request, TopicCoverage.COVERED),
            in_progress=_topics_with(request, TopicCoverage.IN_PROGRESS),
            not_started=_topics_with(request, TopicCoverage.NOT_STARTED),
            opening=not request.turns,
            directive=request.directive.value,
            minutes=max(1, round(request.remaining_s / 60)),
        )

        messages: list[ChatMessage] = []
        pending_user = opening.text
        for turn in request.turns:
            if isinstance(turn, CandidateTurn):
                pending_user = _join(pending_user, f"Candidate: {turn.text or '(no answer)'}")
            else:
                messages.append(ChatMessage("user", pending_user or "(continue)"))
                messages.append(ChatMessage("assistant", _move_json(turn.move)))
                pending_user = ""
        messages.append(ChatMessage("user", _join(pending_user, state.text)))

        chat_request = ChatRequest(
            instructions=system.text,
            messages=tuple(messages),
            temperature=self._temperature,
            top_p=self._top_p,
            max_output_tokens=self._max_output_tokens,
        )
        return chat_request, f"{system.ref}+{opening.ref}+{state.ref}"


def _move_json(move: InterviewerMove) -> str:
    return json.dumps(
        {
            "action": move.action.value,
            "topic_id": move.topic_id,
            "utterance": move.utterance,
            "covered_topic_ids": list(move.covered_topic_ids),
        },
        ensure_ascii=False,
    )


def _topics_with(request: MoveRequest, status: TopicCoverage) -> list[str]:
    return [t.id for t in request.context.topics if request.coverage.get(t.id) is status]


def _join(first: str, second: str) -> str:
    return f"{first}\n\n{second}" if first else second


def _action(value: object) -> MoveAction | None:
    try:
        return MoveAction(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _spoken(text: str) -> str:
    """Remove markdown emphasis, which a speech synthesiser would read aloud."""
    return text.replace("*", "")


def _first_question(text: str) -> str:
    """Text up to and including the first question mark."""
    cut = text.find("?")
    return text if cut == -1 else text[: cut + 1]
