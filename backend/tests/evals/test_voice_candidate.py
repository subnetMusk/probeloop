"""The synthetic voice candidate: answer hand-over, reaction to server messages and the report."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

import httpx
import pytest
from evals.voice_candidate import (
    FRAME_BYTES,
    InboxAnswers,
    Question,
    Run,
    TurnRecord,
    create_session,
    handle,
    parse_args,
    percentile,
    report_markdown,
    summarise,
    word_error_rate,
)

from probeloop.speech.audio import PcmAudio, to_wav


class FakeSocket:
    def __init__(self) -> None:
        self.json: list[dict[str, Any]] = []
        self.audio: list[bytes] = []

    async def send(self, data: str | bytes) -> None:
        if isinstance(data, bytes):
            self.audio.append(data)
        else:
            self.json.append(json.loads(data))


class FixedAnswers:
    def __init__(self, text: str | None) -> None:
        self.text = text
        self.questions: list[Question] = []

    async def answer(self, question: Question) -> str | None:
        self.questions.append(question)
        return self.text


def piper() -> httpx.AsyncClient:
    wav = to_wav(PcmAudio(bytes(2 * 11_025), 22_050))  # 0.5 s at 22.05 kHz

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=wav)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://tts")


def make_run(tmp_path: Path, answers: Any, listen: bool = False) -> Run:
    args = argparse.Namespace(voice="it_IT-paola-medium", listen=listen)
    return Run(args=args, answers=answers, directory=tmp_path)


def state(status: str, phase: str | None) -> dict[str, Any]:
    return {
        "type": "state.changed",
        "seq": 1,
        "status": status,
        "phase": phase,
        "elapsed_s": 30.0,
        "remaining_s": 570.0,
    }


def test_word_error_rate() -> None:
    assert word_error_rate("Ho usato PostgreSQL.", "ho usato postgresql") == 0.0
    assert word_error_rate("uno due tre quattro", "uno tre quattro cinque") == 0.5
    assert word_error_rate("", "") == 0.0


async def test_candidate_creates_the_session_with_approved_context() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/sessions"
        body = json.loads(request.content)
        assert body["snapshot_id"] == "a" * 32
        assert body["interview_type"] == "hr"
        assert body["modality"] == "voice"
        return httpx.Response(201, json={"id": "session-id"})

    args = parse_args(["--snapshot-id", "a" * 32, "--type", "hr"])
    assert args.voice == "it_IT-riccardo-x_low"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://app"
    ) as api:
        assert await create_session(api, args) == "session-id"


def test_summary_and_report() -> None:
    turns = [
        TurnRecord(1, "Domanda?", "Risposta uno.", 2.0, "Risposta uno.", True, 1, 1.5, 0.1),
        TurnRecord(3, "Altra?", "Risposta due.", 2.0, "Risposta tre.", True, 1, 2.5, 0.2),
    ]
    summary = summarise(turns)
    assert summary == {
        "answers": 2,
        "wer_mean": 0.25,
        "wer_max": 0.5,
        "reply_latency_p50_s": 2.0,
        "reply_latency_p95_s": 2.45,
        "reply_latency_max_s": 2.5,
    }
    assert percentile([], 0.5) is None
    meta = {"session_id": "x", "interview_type": "technical", "minutes": 10, "voice": "v"}
    markdown = report_markdown(meta, summary, turns)
    assert "## Turn 3" in markdown
    assert "**Recognised** (WER 50%): Risposta tre." in markdown


async def test_inbox_hands_over_the_question_and_waits_for_the_answer(tmp_path: Path) -> None:
    inbox = InboxAnswers(tmp_path, poll_s=0.01)
    question = Question(turn_seq=3, text="Mi parli di lei?", elapsed_s=12.0, remaining_s=588.0)
    pending = asyncio.ensure_future(inbox.answer(question))
    async with asyncio.timeout(5):
        while not (tmp_path / "turn-0003-question.json").exists():  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    written = json.loads((tmp_path / "turn-0003-question.json").read_text("utf-8"))
    assert written["text"] == "Mi parli di lei?"
    assert not pending.done()
    (tmp_path / "turn-0003-answer.txt").write_text("Sono uno sviluppatore.\n", "utf-8")
    assert await pending == "Sono uno sviluppatore."

    (tmp_path / "turn-0005-answer.txt").write_text("/end", "utf-8")
    assert await inbox.answer(Question(5, "Altro?", 0, 0)) is None


async def test_a_turn_from_question_to_reply(tmp_path: Path) -> None:
    answers = FixedAnswers("Ho lavorato con Python.")
    run = make_run(tmp_path, answers)
    ws = FakeSocket()
    tasks: list[asyncio.Future[None]] = []

    def spawn(coroutine: Awaitable[None]) -> None:
        tasks.append(asyncio.ensure_future(coroutine))

    async with piper() as tts:
        await handle(run, ws, tts, state("ready", None), spawn)  # type: ignore[arg-type]
        assert ws.json[-1]["type"] == "session.start"
        await handle(
            run,
            ws,  # type: ignore[arg-type]
            tts,
            {"type": "interviewer.move.completed", "turn_seq": 0, "utterance": "Mi parli di lei?"},
            spawn,
        )
        await handle(run, ws, tts, {"type": "tts.done"}, spawn)  # type: ignore[arg-type]
        await asyncio.gather(*tasks)
        assert ws.json[-1]["type"] == "playback.finished"

        await handle(run, ws, tts, state("in_progress", "awaiting_candidate"), spawn)  # type: ignore[arg-type]
        assert run.answering is not None
        await run.answering
    assert answers.questions == [Question(1, "Mi parli di lei?", 30.0, 570.0)]
    assert [m["type"] for m in ws.json[-2:]] == ["turn.start", "turn.end"]
    assert sum(len(f) for f in ws.audio) == 16_000  # 0.5 s resampled to 16 kHz PCM16
    assert max(len(f) for f in ws.audio) == FRAME_BYTES

    await handle(run, ws, tts, {"type": "tts.chunk", "duration_s": 1.0}, spawn)  # type: ignore[arg-type]
    await handle(
        run,
        ws,  # type: ignore[arg-type]
        tts,
        {
            "type": "candidate.answer.recorded",
            "turn_seq": 1,
            "text": "Ho lavorato con Python.",
            "complete": True,
        },
        spawn,
    )
    (turn,) = run.turns
    assert turn.wer == 0.0
    assert turn.reply_audio_after_s is not None
    assert turn.answer_audio_s == pytest.approx(0.5)
    ended = await handle(
        run, ws, tts, {"type": "session.ended", "reason": "completed", "failure": None}, spawn
    )  # type: ignore[arg-type]
    assert ended is False
    assert run.end_reason == "completed"


async def test_a_failed_preparation_stops_the_candidate(tmp_path: Path) -> None:
    run = make_run(tmp_path, FixedAnswers("Mai usata."))
    ws = FakeSocket()
    failure = {
        "type": "error",
        "code": "preparation_failed",
        "message": "the speech synthesis service could not use the voice",
    }
    async with piper() as tts:
        assert await handle(run, ws, tts, failure, lambda c: None) is False  # type: ignore[arg-type]
        # Other errors are recorded and the call goes on.
        other = {"type": "error", "code": "stt_failed", "message": "part of the answer"}
        assert await handle(run, ws, tts, other, lambda c: None) is True  # type: ignore[arg-type]
    assert run.end_reason is not None
    assert run.end_reason.startswith("preparation_failed")
    assert run.answering is None


async def test_no_answer_ends_the_call(tmp_path: Path) -> None:
    run = make_run(tmp_path, FixedAnswers(None))
    ws = FakeSocket()
    async with piper() as tts:
        await handle(run, ws, tts, state("in_progress", "awaiting_candidate"), lambda c: None)  # type: ignore[arg-type]
        assert run.answering is not None
        await run.answering
    assert ws.json[-1]["type"] == "session.end"
