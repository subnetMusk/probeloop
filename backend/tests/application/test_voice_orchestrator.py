"""Voice sessions: the orchestrator with fake speech engines and the energy detector."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import replace

import pytest

from probeloop.interview.application.events import (
    AnswerRecorded,
    AnswerTimeWarning,
    ErrorRaised,
    MoveCompleted,
    Preparing,
    SentenceAudio,
    SessionEnded,
    SpeechFinished,
    TranscriptPartial,
    UtteranceDelta,
)
from probeloop.interview.application.orchestrator import SessionOrchestrator
from probeloop.interview.application.voice import RecognitionStatus, VoiceServices
from probeloop.interview.domain.model import (
    CandidateTurn,
    InterviewerMove,
    Language,
    Modality,
    MoveAction,
    Phase,
    SessionStatus,
)
from probeloop.speech.fake import EnergyVad, FakeSpeechToText, FakeTextToSpeech, SttScript
from probeloop.speech.ports import ServiceStatus, SpeechError
from tests.conftest import EventRecorder, FakeClock, MemoryStore, ScriptedInterviewer, make_session
from tests.speech_audio import frames, silence, tone

VOICE = "it_IT-test"
ANSWER = tone(1.0) + silence(0.8) + tone(1.0) + silence(0.8)


def voice_services(
    stt_script: Sequence[SttScript] = (),
    tts_script: Sequence[Exception | None] = (),
    stt_status: RecognitionStatus | None = None,
    **limits: float,
) -> VoiceServices:
    voice = VoiceServices(
        stt=FakeSpeechToText(stt_script),
        tts=FakeTextToSpeech(script=tts_script),
        vad=EnergyVad,
        voices={Language.ITALIAN: VOICE},
        poll_s=0.01,
        **limits,
    )
    if stt_status is not None:
        voice = replace(voice, stt_status=stt_status)
    return voice


def voice_session(
    clock: FakeClock,
    store: MemoryStore,
    recorder: EventRecorder,
    voice: VoiceServices | None = None,
    interviewer: ScriptedInterviewer | None = None,
) -> SessionOrchestrator:
    return SessionOrchestrator(
        make_session(modality=Modality.VOICE),
        interviewer=interviewer or ScriptedInterviewer(),
        store=store,
        clock=clock,
        sink=recorder,
        voice=voice if voice is not None else voice_services(),
    )


async def speak(o: SessionOrchestrator, pcm: bytes) -> list[bool]:
    accepted = []
    for frame in frames(pcm, 0.1):
        accepted.append(await o.audio_frame(frame))
        await asyncio.sleep(0)
    return accepted


async def open_and_listen(o: SessionOrchestrator) -> None:
    await o.start()
    await o.wait_for_move()
    await o.playback_finished()


async def test_a_spoken_turn_from_question_to_reply(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    voice = voice_services(stt_script=["Ho lavorato con Python.", "E con PostgreSQL."])
    o = voice_session(clock, store, recorder, voice)
    await o.start()
    await o.wait_for_move()

    (sentence,) = recorder.of(SentenceAudio)
    assert (sentence.turn_seq, sentence.index, sentence.text) == (0, 0, "Domanda numero 1?")
    assert voice.tts.calls[0][0] == "Ok."  # type: ignore[attr-defined]
    assert sentence.audio.sample_rate == 22_050
    assert recorder.of(SpeechFinished) == [SpeechFinished(turn_seq=0, sentences=1, failed=0)]
    kinds = [type(e) for e in recorder.events]
    assert kinds.index(MoveCompleted) < kinds.index(SpeechFinished)

    await o.playback_finished()
    await o.start_answer()
    assert all(await speak(o, ANSWER))
    await o.end_answer()

    assert [e.text for e in recorder.of(TranscriptPartial)] == [
        "Ho lavorato con Python.",
        "Ho lavorato con Python. E con PostgreSQL.",
    ]
    (recorded,) = recorder.of(AnswerRecorded)
    assert recorded == AnswerRecorded(
        turn_seq=1, text="Ho lavorato con Python. E con PostgreSQL.", complete=True
    )
    answer = o.session.turns[1]
    assert isinstance(answer, CandidateTurn)
    assert answer.text == recorded.text
    assert store.audio[(o.session.id, 1)].data == ANSWER

    await o.wait_for_move()
    assert len(recorder.of(SpeechFinished)) == 2
    assert store.speakers == {
        (o.session.id, 0): "interviewer",
        (o.session.id, 1): "candidate",
        (o.session.id, 2): "interviewer",
    }
    assert store.audio[(o.session.id, 0)].sample_rate == 22_050
    (metrics,) = store.metrics
    assert metrics["answer_turn_seq"] == 1
    assert metrics["answer_audio_s"] == pytest.approx(len(ANSWER) / 32_000, abs=0.01)
    assert metrics["stt_segments"] == 2
    assert metrics["stt_engine"] == "fake:stt"
    assert metrics["tts_voice"] == VOICE
    assert metrics["tts_sentences"] == 1
    for key in ("stt_finalize_s", "llm_first_text_s", "move_recorded_s", "tts_first_audio_s"):
        assert isinstance(metrics[key], float)
        assert metrics[key] >= 0


async def test_frames_outside_the_candidate_turn_are_dropped(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o = voice_session(clock, store, recorder)
    assert await speak(o, tone(0.3)) == [False] * 3  # before the interview starts
    await open_and_listen(o)
    assert await speak(o, tone(0.3)) == [False] * 3  # waiting for "answer"
    await o.start_answer()
    assert all(await speak(o, ANSWER))
    await o.end_answer()
    assert await speak(o, tone(0.3)) == [False] * 3  # the interviewer is replying
    assert o.dropped_frames == 9
    assert store.audio[(o.session.id, 1)].data == ANSWER


async def test_start_loads_the_model_the_recogniser_and_the_voice(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    states = iter(["starting", "starting", "ready"])

    async def worker_loading() -> ServiceStatus:
        return ServiceStatus(next(states), "the speech recognition service is still loading")

    voice = voice_services(stt_status=worker_loading)
    o = voice_session(clock, store, recorder, voice)
    await o.start()
    await o.wait_for_move()
    first, *_, last = recorder.of(Preparing)
    assert {s.name: s.state for s in first.steps} == {
        "language_model": "loading",
        "speech_recognition": "loading",
        "speech_synthesis": "loading",
    }
    assert {s.state for s in last.steps} == {"ready"}
    assert last.progress == 1.0
    assert isinstance(voice.tts, FakeTextToSpeech)
    assert voice.tts.calls[0] == ("Ok.", VOICE)  # the voice is loaded before the first question
    assert o.session.status is SessionStatus.IN_PROGRESS


async def test_the_interview_does_not_start_while_a_speech_service_is_down(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    async def worker_failed() -> ServiceStatus:
        return ServiceStatus("failed", "the speech recognition service is not working")

    o = voice_session(clock, store, recorder, voice_services(stt_status=worker_failed))
    await o.start()
    await o.wait_for_move()
    (error,) = recorder.of(ErrorRaised)
    assert error.code == "preparation_failed"
    assert "not working" in error.message
    steps = {s.name: s for s in recorder.of(Preparing)[-1].steps}
    assert steps["speech_recognition"].state == "failed"
    assert steps["language_model"].state == "ready"
    assert o.session.status is SessionStatus.READY


async def test_a_service_still_starting_after_the_timeout_fails_the_start(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    async def never_ready() -> ServiceStatus:
        return ServiceStatus("starting", "the speech recognition service is unreachable")

    voice = replace(voice_services(stt_status=never_ready), ready_timeout_s=0.05)
    o = voice_session(clock, store, recorder, voice)
    await o.start()
    await o.wait_for_move()
    assert "unreachable" in recorder.of(ErrorRaised)[0].message
    assert o.session.status is SessionStatus.READY


async def test_without_speech_services_a_voice_interview_cannot_start(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o = SessionOrchestrator(
        make_session(modality=Modality.VOICE),
        interviewer=ScriptedInterviewer(),
        store=store,
        clock=clock,
        sink=recorder,
    )
    await o.start()
    await o.wait_for_move()
    assert recorder.of(ErrorRaised)[0].code == "preparation_failed"
    assert o.session.status is SessionStatus.READY


async def test_a_long_answer_is_warned_and_then_ended(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    voice = voice_services(answer_warning_s=1.0, answer_limit_s=2.0)
    o = voice_session(clock, store, recorder, voice)
    await open_and_listen(o)
    await o.start_answer()
    accepted = await speak(o, tone(3.0))
    assert accepted[:20] == [True] * 20  # the answer ends after 2 s of audio
    assert not any(accepted[20:])
    (warning,) = recorder.of(AnswerTimeWarning)
    assert warning.turn_seq == 1
    assert warning.remaining_s == pytest.approx(1.0, abs=0.11)
    assert len(recorder.of(AnswerRecorded)) == 1
    assert store.audio[(o.session.id, 1)].duration_s == pytest.approx(2.0, abs=0.01)


async def test_an_answer_interrupted_by_a_pause_continues_after_resume(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o = voice_session(clock, store, recorder)
    await open_and_listen(o)
    await o.start_answer()
    await speak(o, tone(1.0))
    await o.pause()
    assert await speak(o, tone(0.5)) == [False] * 5  # paused: dropped
    await o.resume()
    assert o.session.phase is Phase.AWAITING_CANDIDATE
    await o.start_answer()
    await speak(o, silence(0.8) + tone(1.0) + silence(0.8))
    await o.end_answer()
    assert len([t for t in o.session.turns if isinstance(t, CandidateTurn)]) == 1
    expected = tone(1.0) + silence(0.8) + tone(1.0) + silence(0.8)
    assert store.audio[(o.session.id, 1)].data == expected


async def test_ending_the_call_during_an_answer_discards_it(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o = voice_session(clock, store, recorder)
    await open_and_listen(o)
    await o.start_answer()
    await speak(o, tone(1.0))
    await o.end()
    assert o.session.status is SessionStatus.ENDED
    assert recorder.of(AnswerRecorded) == []
    assert "candidate" not in store.speakers.values()
    assert store.exports == [o.session.id]


async def test_a_sentence_that_cannot_be_spoken_is_reported(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    # The warm-up sentence works; the question fails twice.
    voice = voice_services(tts_script=[None, SpeechError("down"), SpeechError("down")])
    o = voice_session(clock, store, recorder, voice)
    await o.start()
    await o.wait_for_move()
    assert [e.code for e in recorder.of(ErrorRaised)] == ["tts_failed"]
    assert recorder.of(SpeechFinished) == [SpeechFinished(turn_seq=0, sentences=0, failed=1)]
    assert recorder.of(MoveCompleted)[0].utterance == "Domanda numero 1?"


async def test_an_answer_that_cannot_be_transcribed_is_kept_as_incomplete(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    voice = voice_services(stt_script=[SpeechError("down"), SpeechError("down"), "Seconda."])
    o = voice_session(clock, store, recorder, voice)
    await open_and_listen(o)
    await o.start_answer()
    await speak(o, ANSWER)
    await o.end_answer()
    assert "stt_failed" in [e.code for e in recorder.of(ErrorRaised)]
    assert recorder.of(AnswerRecorded) == [
        AnswerRecorded(turn_seq=1, text="Seconda.", complete=False)
    ]
    assert store.audio[(o.session.id, 1)].data == ANSWER


async def test_answers_must_match_the_modality(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    o = voice_session(clock, store, recorder)
    await open_and_listen(o)
    await o.start_answer()
    with pytest.raises(ValueError, match="spoken answers"):
        await o.end_answer("typed")

    text = SessionOrchestrator(
        make_session(),
        interviewer=ScriptedInterviewer(),
        store=store,
        clock=clock,
        sink=EventRecorder(),
        voice=voice_services(),
    )
    await open_and_listen(text)
    await text.start_answer()
    assert await text.audio_frame(tone(0.1)) is False
    with pytest.raises(ValueError, match="answer text"):
        await text.end_answer()
    assert recorder.of(SentenceAudio)  # the voice session spoke
    assert "candidate" not in store.speakers.values()


async def test_ending_the_call_while_the_answer_is_transcribed_stops_the_reply(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    stt = FakeSpeechToText(delay_s=0.1)
    voice = VoiceServices(
        stt=stt, tts=FakeTextToSpeech(), vad=EnergyVad, voices={Language.ITALIAN: VOICE}
    )
    slow_llm = ScriptedInterviewer(chunk_delay_s=0.01)  # the reply streams for a while
    o = voice_session(clock, store, recorder, voice, interviewer=slow_llm)
    await open_and_listen(o)
    await o.start_answer()
    await speak(o, ANSWER)
    finishing = asyncio.create_task(o.end_answer())
    await asyncio.sleep(0.01)  # the transcript is being finalised under the lock
    await o.end()
    await finishing
    await o.wait_for_move()
    assert o.session.status is SessionStatus.ENDED
    ended = next(i for i, e in enumerate(recorder.events) if isinstance(e, SessionEnded))
    after = recorder.events[ended:]
    assert not any(isinstance(e, MoveCompleted | SentenceAudio | UtteranceDelta) for e in after)
    assert len(recorder.of(MoveCompleted)) == 1  # only the opening question


async def test_the_farewell_is_spoken_too(
    clock: FakeClock, store: MemoryStore, recorder: EventRecorder
) -> None:
    def farewell(_: object) -> InterviewerMove:
        return InterviewerMove(MoveAction.END, "t1", "Grazie. Il colloquio è terminato.")

    o = voice_session(clock, store, recorder, interviewer=ScriptedInterviewer(farewell))
    await o.start()
    await o.wait_for_move()
    assert [e.text for e in recorder.of(SentenceAudio)] == [
        "Grazie.",
        "Il colloquio è terminato.",
    ]
    await o.playback_finished()
    assert o.session.status is SessionStatus.ENDED
    assert store.exports == [o.session.id]  # once, before SessionEnded reaches the client
