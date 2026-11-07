from __future__ import annotations

import pytest

from probeloop.interview.application.transcripts import TranscriptService
from probeloop.interview.domain.model import (
    EndReason,
    InterviewerMove,
    InterviewSession,
    InvalidTransitionError,
    Modality,
    MoveAction,
    RevisionSource,
    Speaker,
)
from probeloop.platform.jobs import Job, JobError, JobStatus
from probeloop.speech.audio import PcmAudio
from probeloop.speech.fake import FakeSpeechToText
from probeloop.speech.ports import SpeechError
from tests.conftest import FakeClock, MemoryStore, make_session
from tests.speech_audio import tone

SID = "f" * 32


def answered(answers: int = 2) -> InterviewSession:
    s = make_session(session_id=SID, modality=Modality.VOICE)
    s.start(0)
    for n in range(answers):
        s.record_move(InterviewerMove(MoveAction.FOLLOW_UP, "t1", f"Domanda {n}?"), 1)
        s.finish_speaking(2)
        s.start_answer(3)
        s.finish_answer(4)
        s.record_answer(f"risposta dal vivo {n}", 5, engine_ref="stt-worker/live")
    s.end(EndReason.USER_ENDED, 10)
    return s


def job() -> Job:
    return Job(
        id="j", kind="refine_transcript", subject_id=SID, status=JobStatus.RUNNING, created_at=0
    )


async def no_progress(fraction: float, message: str | None) -> None:
    pass


async def test_refinement_adds_a_revision_with_words_to_every_answer_with_audio() -> None:
    store = MemoryStore()
    await store.save(answered())
    await store.save_turn_audio(SID, 1, Speaker.CANDIDATE, PcmAudio(tone(1.0)))
    await store.save_turn_audio(SID, 3, Speaker.CANDIDATE, PcmAudio(tone(0.1)))  # too short
    refiner = FakeSpeechToText(script=["Uso FastAPI e PostgreSQL."])
    service = TranscriptService(
        store=store, clock=FakeClock(), refiner=refiner, vocabulary=lambda _: "FastAPI"
    )
    seen: list[float] = []

    async def progress(fraction: float, message: str | None) -> None:
        seen.append(fraction)

    result = await service.refine(job(), progress)

    assert result == {"revised": 1, "skipped": 1, "vocabulary": True}
    assert seen == [0.5, 1.0]
    options = refiner.calls[0][1]
    assert (options.language, options.initial_prompt, options.word_timestamps) == (
        "it",
        "FastAPI",
        True,
    )
    session = await store.load(SID)
    assert session is not None
    first, second = session.candidate_turns()
    assert first.text == "Uso FastAPI e PostgreSQL."
    assert first.current.source is RevisionSource.RETRANSCRIPTION
    assert first.current.engine_ref == "fake:stt"
    assert [w.text for w in first.current.words] == ["Uso", "FastAPI", "e", "PostgreSQL."]
    assert len(second.revisions) == 1  # untouched
    assert store.exports == [SID]


async def test_hallucinated_text_does_not_replace_the_live_transcript() -> None:
    store = MemoryStore()
    await store.save(answered(1))
    await store.save_turn_audio(SID, 1, Speaker.CANDIDATE, PcmAudio(tone(1.0)))
    refiner = FakeSpeechToText(script=["Sottotitoli creati dalla comunità Amara.org"])
    service = TranscriptService(store=store, clock=FakeClock(), refiner=refiner)
    result = await service.refine(job(), no_progress)
    assert result["revised"] == 0
    session = await store.load(SID)
    assert session is not None
    assert session.candidate_turns()[0].text == "risposta dal vivo 0"


async def test_recogniser_failures_fail_the_job() -> None:
    store = MemoryStore()
    await store.save(answered(1))
    await store.save_turn_audio(SID, 1, Speaker.CANDIDATE, PcmAudio(tone(1.0)))
    refiner = FakeSpeechToText(script=[SpeechError("worker down")])
    service = TranscriptService(store=store, clock=FakeClock(), refiner=refiner)
    with pytest.raises(JobError, match="speech recognition failed"):
        await service.refine(job(), no_progress)


async def test_an_edit_becomes_a_new_revision_and_rewrites_the_exports() -> None:
    store = MemoryStore()
    await store.save(answered(1))
    service = TranscriptService(store=store, clock=FakeClock())
    turn = await service.edit(SID, 1, "  risposta   corretta ")
    assert (turn.text, turn.current.source, turn.current.number) == (
        "risposta corretta",
        RevisionSource.USER_EDIT,
        2,
    )
    assert store.exports == [SID]
    with pytest.raises(ValueError, match="limited"):
        await service.edit(SID, 1, "x" * 10_001)


async def test_answers_of_a_running_interview_cannot_be_edited() -> None:
    store = MemoryStore()
    s = make_session(session_id=SID)
    s.start(0)
    await store.save(s)
    service = TranscriptService(store=store, clock=FakeClock())
    with pytest.raises(InvalidTransitionError):
        await service.edit(SID, 1, "x")
