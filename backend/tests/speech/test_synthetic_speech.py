"""TurnTranscriber with the real Silero detector on synthetic Piper speech.

The recogniser is a fake that finds each segment inside the fixture and returns the sentences
the segment contains, so the final text shows whether segmentation lost, split or duplicated a
sentence. Recognition accuracy itself is measured on the real engines, not here.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import pytest

from probeloop.speech.audio import SAMPLE_RATE, PcmAudio
from probeloop.speech.ports import (
    RecognizedSegment,
    TranscribeOptions,
    Transcription,
)
from probeloop.speech.silero import SileroVad
from probeloop.speech.transcriber import TurnTranscriber, TurnTranscript
from tests.speech_audio import SpeechFixture, frames, noise, speech_fixture

OPTIONS = TranscribeOptions(language="it")


@dataclass
class LocatingStt:
    """Returns the fixture sentences that lie entirely inside the transcribed audio."""

    fixture: SpeechFixture
    calls: list[tuple[float, float]] = field(default_factory=list)

    @property
    def engine_ref(self) -> str:
        return "test:locating"

    async def transcribe(self, audio: PcmAudio, options: TranscribeOptions) -> Transcription:
        offset = self.fixture.audio.data.find(audio.data)
        assert offset >= 0, "segment audio must be a slice of the stream"
        assert offset % 2 == 0
        start = offset / 2 / SAMPLE_RATE
        end = start + audio.duration_s
        self.calls.append((start, end))
        text = " ".join(
            u.text for u in self.fixture.utterances if u.start_s >= start and u.end_s <= end
        )
        segments = (RecognizedSegment(0.0, audio.duration_s, text),) if text else ()
        return Transcription(segments, options.language, self.engine_ref)


async def transcribe(fixture: SpeechFixture, frame_s: float = 0.02) -> TurnTranscript:
    t = TurnTranscriber(LocatingStt(fixture), SileroVad(), OPTIONS)
    t.start()
    for frame in frames(fixture.audio.data, frame_s):
        t.push(frame)
    return await t.finish()


def gaps(fixture: SpeechFixture) -> list[tuple[float, float]]:
    u = fixture.utterances
    return [(a.end_s, b.start_s) for a, b in itertools.pairwise(u)]


async def test_answers_separated_by_pauses_become_one_segment_each() -> None:
    fixture = speech_fixture("three_sentences")
    result = await transcribe(fixture)
    assert result.text == fixture.text
    assert len(result.segments) == 3
    assert not any(s.forced for s in result.segments)
    for segment, utterance in zip(result.segments, fixture.utterances, strict=True):
        assert segment.start_s == pytest.approx(utterance.start_s, abs=0.3)
        assert segment.end_s == pytest.approx(utterance.end_s, abs=0.3)


async def test_a_long_answer_is_cut_at_a_pause_before_15_s() -> None:
    fixture = speech_fixture("long_answer")
    result = await transcribe(fixture)
    assert result.text == fixture.text  # no sentence was split or lost
    assert len(result.segments) == 2
    first, second = result.segments
    assert first.forced
    assert first.end_s - first.start_s <= 15.0
    assert any(a <= first.end_s <= b for a, b in gaps(fixture))
    assert second.start_s == pytest.approx(first.end_s)


async def test_thinking_before_answering_is_not_transcribed() -> None:
    fixture = speech_fixture("late_start")
    result = await transcribe(fixture)
    assert result.text == fixture.text
    (segment,) = result.segments
    assert segment.start_s == pytest.approx(fixture.utterances[0].start_s, abs=0.3)


@pytest.mark.parametrize("frame_s", [0.01, 0.128, 0.5])
async def test_frame_size_does_not_matter(frame_s: float) -> None:
    fixture = speech_fixture("three_sentences")
    result = await transcribe(fixture, frame_s)
    assert result.text == fixture.text
    assert len(result.segments) == 3


async def test_two_minutes_of_silence_produce_no_text() -> None:
    quiet_room = noise(120.0, rms=0.001, seed=7)  # about -60 dBFS
    stt = LocatingStt(speech_fixture("late_start"))
    t = TurnTranscriber(stt, SileroVad(), OPTIONS)
    t.start()
    for frame in frames(quiet_room, 0.1):
        t.push(frame)
    result = await t.finish()
    assert stt.calls == []
    assert result.text == ""
    assert result.discarded_bursts == 0
