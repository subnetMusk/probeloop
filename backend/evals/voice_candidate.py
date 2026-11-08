"""A synthetic candidate for voice interviews against the running stack.

It takes part in a real voice interview the way the browser does: it creates the session, starts
it, listens to the interviewer (waiting as long as the audio would play), and answers out loud.
Answers are synthesised with Piper, in a voice different from the interviewer's, resampled to
16 kHz and streamed in real time in 100 ms frames between "answer" and "end of answer".

Who writes the answers is pluggable (`AnswerSource`). The only source so far is an inbox: every
question is written to `<run>/turn-NNNN-question.json`, and the run waits for the answer in
`<run>/turn-NNNN-answer.txt` (write `/end` to end the call). An agent or a person can play the
candidate that way, without scripted answers.

The run directory also receives `events.jsonl`, and at the end `report.json` and `report.md`:
for every turn, what was said, what the recogniser heard (with WER), and the latency from "end of
answer" to the first audio of the reply, plus their summary.

    docker compose --profile tools run --rm voice-candidate --minutes 10

Answers are synthetic speech: recognition errors partly come from Piper's pronunciation (for
example of English technical terms), not only from the recogniser.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from websockets.asyncio.client import ClientConnection, connect

from probeloop.speech.arrays import resample
from probeloop.speech.audio import SAMPLE_RATE, from_wav
from probeloop.speech.filters import normalise

FRAME_BYTES = 2 * SAMPLE_RATE // 10  # 100 ms of 16 kHz PCM16, like the browser
END_CALL = "/end"


# ---------------------------------------------------------------------- answers


@dataclass(frozen=True)
class Question:
    turn_seq: int  # the turn the answer will have
    text: str  # everything the interviewer said since the last answer
    elapsed_s: float
    remaining_s: float


class AnswerSource(Protocol):
    async def answer(self, question: Question) -> str | None:
        """The answer to speak, or None to end the call."""
        ...


@dataclass
class InboxAnswers:
    """Hands each question over as a file and waits for the answer file."""

    directory: Path
    poll_s: float = 0.5
    timeout_s: float = 1800.0

    async def answer(self, question: Question) -> str | None:
        stem = self.directory / f"turn-{question.turn_seq:04d}"
        handed = json.dumps(asdict(question), ensure_ascii=False, indent=2)
        await asyncio.to_thread(Path(f"{stem}-question.json").write_text, handed, "utf-8")
        reply = Path(f"{stem}-answer.txt")
        deadline = time.monotonic() + self.timeout_s
        while not await asyncio.to_thread(reply.exists):
            if time.monotonic() > deadline:
                return None
            await asyncio.sleep(self.poll_s)
        await asyncio.sleep(0.2)  # let the writer finish
        text = (await asyncio.to_thread(reply.read_text, "utf-8")).strip()
        return None if text == END_CALL else text


# ---------------------------------------------------------------------- report


@dataclass
class TurnRecord:
    turn_seq: int
    question: str
    answer: str
    answer_audio_s: float = 0.0
    recognised: str | None = None
    complete: bool | None = None
    partials: int = 0
    reply_audio_after_s: float | None = None  # "end of answer" to the first audio of the reply
    recorded_after_s: float | None = None  # "end of answer" to the final transcript

    @property
    def wer(self) -> float | None:
        return None if self.recognised is None else word_error_rate(self.answer, self.recognised)


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Word-level edit distance over the number of reference words, after normalisation."""
    ref, hyp = normalise(reference).split(), normalise(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    row = list(range(len(hyp) + 1))
    for i, word in enumerate(ref, 1):
        previous, row[0] = row[0], i
        for j, other in enumerate(hyp, 1):
            current = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1, previous + (word != other))
            previous = current
    return row[-1] / len(ref)


def percentile(values: list[float], share: float) -> float | None:
    """Linear interpolation between the closest ranks, as NumPy's default."""
    if not values:
        return None
    ordered = sorted(values)
    position = share * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 3)


def summarise(turns: list[TurnRecord]) -> dict[str, Any]:
    latencies = [t.reply_audio_after_s for t in turns if t.reply_audio_after_s is not None]
    errors = [w for t in turns if (w := t.wer) is not None]
    return {
        "answers": len(turns),
        "wer_mean": round(statistics.fmean(errors), 3) if errors else None,
        "wer_max": round(max(errors), 3) if errors else None,
        "reply_latency_p50_s": percentile(latencies, 0.5),
        "reply_latency_p95_s": percentile(latencies, 0.95),
        "reply_latency_max_s": max(latencies) if latencies else None,
    }


def report_markdown(meta: dict[str, Any], summary: dict[str, Any], turns: list[TurnRecord]) -> str:
    def seconds(value: float | None) -> str:
        return "-" if value is None else f"{value:.2f} s"

    lines = [
        "# Voice candidate run",
        "",
        f"Session `{meta['session_id']}`, {meta['interview_type']}, {meta['minutes']} minutes, "
        f"candidate voice {meta['voice']}. Ended: {meta.get('end_reason') or '-'}.",
        "",
        f"- Answers: {summary['answers']}",
        f"- Mean WER of the recognised answers: {summary['wer_mean']}",
        f"- Reply latency p50 / p95 / max: {seconds(summary['reply_latency_p50_s'])} / "
        f"{seconds(summary['reply_latency_p95_s'])} / {seconds(summary['reply_latency_max_s'])}",
        "",
    ]
    for t in turns:
        wer = "-" if t.wer is None else f"{t.wer:.0%}"
        lines += [
            f"## Turn {t.turn_seq}",
            "",
            f"**Interviewer:** {t.question}",
            "",
            f"**Said** ({t.answer_audio_s:.1f} s): {t.answer}",
            "",
            f"**Recognised** (WER {wer}): {t.recognised}",
            "",
            f"Reply audio after {seconds(t.reply_audio_after_s)}; "
            f"final transcript after {seconds(t.recorded_after_s)}.",
            "",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------- the run


@dataclass
class Run:
    args: argparse.Namespace
    answers: AnswerSource
    directory: Path
    session_id: str = ""
    turns: list[TurnRecord] = field(default_factory=list)
    utterance: str = ""
    last_move_seq: int = -1
    playback_until: float = 0.0
    answering: asyncio.Task[None] | None = None
    ended_at: float | None = None
    end_reason: str | None = None
    started: bool = False

    def log(self, kind: str, **fields: Any) -> None:
        line = {"t": round(time.time(), 3), "kind": kind, **fields}
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


async def synthesize(client: httpx.AsyncClient, text: str, voice: str) -> bytes:
    response = await client.post("/synthesize", json={"text": text, "voice": voice})
    response.raise_for_status()
    return resample(from_wav(response.content), SAMPLE_RATE).data


async def create_session(api: httpx.AsyncClient, args: argparse.Namespace) -> str:
    created = await api.post(
        "/api/sessions",
        json={
            "interview_type": args.type,
            "difficulty": args.difficulty,
            "language": args.language,
            "modality": "voice",
            "duration_minutes": args.minutes,
            "snapshot_id": args.snapshot_id,
        },
    )
    created.raise_for_status()
    return str(created.json()["id"])


async def send(ws: ClientConnection, kind: str, **fields: Any) -> None:
    await ws.send(json.dumps({"type": kind, "client_msg_id": uuid.uuid4().hex, **fields}))


async def answer_turn(
    run: Run, ws: ClientConnection, piper: httpx.AsyncClient, question: Question
) -> None:
    text = await run.answers.answer(question)
    if text is None:
        run.log("end_call")
        await send(ws, "session.end")
        return
    pcm = await synthesize(piper, text, run.args.voice)
    record = TurnRecord(question.turn_seq, question.text, text, answer_audio_s=len(pcm) / 32_000)
    run.turns.append(record)
    await send(ws, "turn.start")
    start = time.monotonic()
    for offset in range(0, len(pcm), FRAME_BYTES):
        await asyncio.sleep(max(0.0, start + offset / 32_000 - time.monotonic()))
        await ws.send(pcm[offset : offset + FRAME_BYTES])
    await send(ws, "turn.end")
    run.ended_at = time.monotonic()
    run.log("answer_sent", turn_seq=question.turn_seq, audio_s=record.answer_audio_s)


def play(run: Run, chunk_s: float) -> None:
    """Account for the audio as if it were played back to back."""
    now = time.monotonic()
    run.playback_until = max(run.playback_until, now) + (chunk_s if run.args.listen else 0.0)


async def finish_playback(run: Run, ws: ClientConnection) -> None:
    await asyncio.sleep(max(0.0, run.playback_until - time.monotonic()))
    await send(ws, "playback.finished")


async def handle(
    run: Run,
    ws: ClientConnection,
    piper: httpx.AsyncClient,
    message: dict[str, Any],
    spawn: Callable[[Awaitable[None]], None],
) -> bool:
    """React to one server message. False once the session has ended."""
    kind = message["type"]
    last = run.turns[-1] if run.turns else None
    if kind == "state.changed":
        if message["status"] == "ready" and not run.started:
            run.started = True
            await send(ws, "session.start")
        elif message["phase"] == "awaiting_candidate" and (
            run.answering is None or run.answering.done()
        ):
            question = Question(
                turn_seq=run.last_move_seq + 1,
                text=run.utterance.strip(),
                elapsed_s=message["elapsed_s"],
                remaining_s=message["remaining_s"],
            )
            run.utterance = ""
            run.answering = asyncio.ensure_future(answer_turn(run, ws, piper, question))
    elif kind == "session.preparing":
        run.log("preparing", progress=message["progress"], steps=message["steps"])
    elif kind == "interviewer.move.completed":
        run.utterance += " " + message["utterance"]
        run.last_move_seq = message["turn_seq"]
        run.log("question", turn_seq=message["turn_seq"], text=message["utterance"])
    elif kind == "tts.chunk":
        if last is not None and last.reply_audio_after_s is None and run.ended_at is not None:
            last.reply_audio_after_s = round(time.monotonic() - run.ended_at, 3)
        play(run, message["duration_s"])
    elif kind == "tts.done":
        spawn(finish_playback(run, ws))
    elif kind == "transcript.partial" and last is not None:
        last.partials += 1
    elif kind == "candidate.answer.recorded" and last is not None:
        last.recognised = message["text"]
        last.complete = message["complete"]
        if run.ended_at is not None:
            last.recorded_after_s = round(time.monotonic() - run.ended_at, 3)
        run.log("recognised", turn_seq=message["turn_seq"], text=message["text"])
    elif kind == "error":
        run.log("error", code=message["code"], message=message["message"])
    elif kind == "session.ended":
        run.end_reason = message["reason"] or message["failure"]
        return False
    return True


async def main_async(args: argparse.Namespace) -> int:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    directory = args.io / f"run-{stamp}"
    directory.mkdir(parents=True)
    run = Run(args=args, answers=InboxAnswers(directory), directory=directory)
    background: set[asyncio.Task[None]] = set()

    def spawn(coroutine: Awaitable[None]) -> None:
        task = asyncio.ensure_future(coroutine)
        background.add(task)
        task.add_done_callback(background.discard)

    base = args.url.rstrip("/")
    async with (
        httpx.AsyncClient(base_url=base, timeout=180) as api,
        httpx.AsyncClient(base_url=args.piper_url, timeout=60) as piper,
    ):
        run.session_id = await create_session(api, args)
        print(f"session {run.session_id}; questions and answers in {directory}", flush=True)
        ws_url = base.replace("http", "ws", 1) + f"/ws/sessions/{run.session_id}"
        async with connect(ws_url, max_size=None) as ws:
            await send(ws, "session.join", last_seq=0)
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue  # the interviewer's audio: only its duration matters here
                if not await handle(run, ws, piper, json.loads(raw), spawn):
                    break
        session = (await api.get(f"/api/sessions/{run.session_id}")).json()

    meta = {
        "session_id": run.session_id,
        "interview_type": args.type,
        "minutes": args.minutes,
        "voice": args.voice,
        "snapshot_id": args.snapshot_id,
        "end_reason": run.end_reason,
    }
    summary = summarise(run.turns)
    report = {**meta, "summary": summary, "turns": [asdict(t) | {"wer": t.wer} for t in run.turns]}
    report["session"] = session
    (directory / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (directory / "report.md").write_text(report_markdown(meta, summary, run.turns), "utf-8")
    print(json.dumps(summary), flush=True)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evals.voice_candidate", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="the backend")
    parser.add_argument("--piper-url", default="http://tts-piper:5000")
    parser.add_argument("--voice", default="it_IT-riccardo-x_low", help="the candidate's voice")
    parser.add_argument("--snapshot-id", help="approved context from the document wizard")
    parser.add_argument(
        "--type", default="technical", choices=["hr", "behavioral", "technical", "mixed"]
    )
    parser.add_argument("--difficulty", default="medium", choices=["easy", "medium", "hard"])
    parser.add_argument("--language", default="it", choices=["it", "en"])
    parser.add_argument("--minutes", type=int, default=10)
    parser.add_argument("--io", type=Path, default=Path("/io"), help="where runs are written")
    parser.add_argument(
        "--no-listen",
        dest="listen",
        action="store_false",
        help="report playback as finished at once instead of after the audio's duration",
    )
    return parser.parse_args(argv)


def main() -> None:
    raise SystemExit(asyncio.run(main_async(parse_args())))


if __name__ == "__main__":
    main()
