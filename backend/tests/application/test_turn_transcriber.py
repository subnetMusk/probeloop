"""TurnTranscriber with the deterministic energy detector and the fake recogniser."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from probeloop.speech.fake import EnergyVad, FakeSpeechToText
from probeloop.speech.ports import SpeechError, TranscribeOptions
from probeloop.speech.transcriber import (
    PartialTranscript,
    SegmentFailed,
    TranscriberClosedError,
    TranscriberEvent,
    TurnTranscriber,
)
from tests.speech_audio import frames, silence, tone

OPTIONS = TranscribeOptions(language="it", initial_prompt="FastAPI, PostgreSQL")

# Three bursts of "speech" separated by pauses long enough to close a segment.
ANSWER = silence(0.3) + tone(1.0) + silence(0.8) + tone(1.5) + silence(0.8) + tone(0.7)


@dataclass
class Events:
    items: list[TranscriberEvent] = field(default_factory=list)

    async def __call__(self, event: TranscriberEvent) -> None:
        self.items.append(event)


def transcriber(stt: FakeSpeechToText, events: Events | None = None) -> TurnTranscriber:
    t = TurnTranscriber(stt, EnergyVad(), OPTIONS, sink=events)
    t.start()
    return t


async def speak(t: TurnTranscriber, pcm: bytes) -> None:
    for frame in frames(pcm):
        t.push(frame)
        await asyncio.sleep(0)


async def test_segments_are_transcribed_while_the_candidate_speaks() -> None:
    stt = FakeSpeechToText(["Prima parte.", "Seconda parte.", "Terza parte."])
    events = Events()
    t = transcriber(stt, events)

    await speak(t, ANSWER)
    for _ in range(100):  # the first two segments close at their pauses
        if len(events.items) == 2:
            break
        await asyncio.sleep(0.01)
    assert [e.text for e in events.items if isinstance(e, PartialTranscript)] == [
        "Prima parte.",
        "Prima parte. Seconda parte.",
    ]

    result = await t.finish()
    assert result.text == "Prima parte. Seconda parte. Terza parte."
    assert [s.index for s in result.segments] == [0, 1, 2]
    assert result.segments[0].start_s == pytest.approx(0.1, abs=0.04)
    assert result.segments[2].end_s == pytest.approx(len(ANSWER) / 32_000, abs=0.04)
    assert result.complete
    assert result.audio.data == ANSWER
    assert result.engine_ref == "fake:stt"
    assert result.finalize_s >= 0
    assert all(options == OPTIONS for _, options in stt.calls)
    assert len(events.items) == 3


async def test_silence_never_reaches_the_recogniser() -> None:
    stt = FakeSpeechToText()
    t = transcriber(stt)
    await speak(t, silence(5.0))
    result = await t.finish()
    assert stt.calls == []
    assert result.text == ""
    assert result.segments == ()
    assert len(result.audio.data) == len(silence(5.0))


async def test_hallucinated_text_is_dropped() -> None:
    stt = FakeSpeechToText(["Sottotitoli creati dalla comunità Amara.org", "Risposta vera."])
    events = Events()
    t = transcriber(stt, events)
    await speak(t, tone(1.0) + silence(0.8) + tone(1.0))
    result = await t.finish()
    assert result.text == "Risposta vera."
    assert [(d.index, d.reason) for d in result.dropped] == [(0, "blocklist")]
    assert [e.segment.index for e in events.items if isinstance(e, PartialTranscript)] == [1]


async def test_a_failed_call_is_retried() -> None:
    stt = FakeSpeechToText([SpeechError("worker busy"), "Ripetuto."])
    t = transcriber(stt)
    await speak(t, tone(1.0))
    result = await t.finish()
    assert result.text == "Ripetuto."
    assert len(stt.calls) == 2


async def test_a_segment_that_keeps_failing_is_reported_and_the_rest_continues() -> None:
    stt = FakeSpeechToText([SpeechError("down"), SpeechError("down"), "Dopo il guasto."])
    events = Events()
    t = transcriber(stt, events)
    await speak(t, tone(1.0) + silence(0.8) + tone(1.0))
    result = await t.finish()
    assert result.text == "Dopo il guasto."
    assert not result.complete
    assert [f.index for f in result.failed] == [0]
    assert isinstance(events.items[0], SegmentFailed)
    assert len(result.audio.data) == len(tone(1.0) + silence(0.8) + tone(1.0))


async def test_finalisation_waits_for_the_last_segment() -> None:
    stt = FakeSpeechToText(["Fine."], delay_s=0.05)
    t = transcriber(stt)
    await speak(t, tone(1.0))
    result = await t.finish()
    assert result.text == "Fine."
    assert result.finalize_s >= 0.05


async def test_a_broken_listener_does_not_stop_the_transcription() -> None:
    async def broken(event: TranscriberEvent) -> None:
        raise RuntimeError("client gone")

    t = TurnTranscriber(FakeSpeechToText(["Uno."]), EnergyVad(), OPTIONS, sink=broken)
    t.start()
    await speak(t, tone(1.0))
    assert (await t.finish()).text == "Uno."


async def test_cancel_keeps_all_received_audio() -> None:
    stt = FakeSpeechToText(delay_s=0.5)
    t = transcriber(stt)
    for frame in frames(ANSWER):
        t.push(frame)  # no yield: frames are still queued when the turn is cancelled
    audio = await t.cancel()
    assert audio.data == ANSWER
    with pytest.raises(TranscriberClosedError):
        t.push(tone(0.1))


async def test_a_turn_finishes_only_once() -> None:
    t = transcriber(FakeSpeechToText())
    await t.finish()
    with pytest.raises(TranscriberClosedError):
        await t.finish()
    with pytest.raises(TranscriberClosedError):
        t.push(tone(0.1))


async def test_odd_frames_are_rejected() -> None:
    t = transcriber(FakeSpeechToText())
    with pytest.raises(ValueError, match="even number"):
        t.push(b"\x00\x01\x02")
    await t.cancel()
