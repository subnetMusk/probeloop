from __future__ import annotations

from dataclasses import replace

import pytest

from probeloop.assessment.application.delivery import DeliveryAnalyser, activity
from probeloop.interview.domain.model import Speaker
from probeloop.speech.audio import PcmAudio
from tests.assessment.support import synthetic_session


class Detector:
    def __init__(self) -> None:
        self.index = 0

    def speech_probability(self, window: bytes) -> float:
        self.index += 1
        return 1.0 if self.index in (2, 37) else 0.0


def test_vad_counts_only_long_internal_pauses() -> None:
    audio = PcmAudio(b"\0\0" * 512 * 40)
    result = activity(audio, Detector())
    assert result.speech_s == pytest.approx(0.064)
    assert result.first_s == pytest.approx(0.032)
    assert result.long_pauses == 1
    assert result.pause_s == pytest.approx(1.088)
    with pytest.raises(ValueError, match="16 kHz"):
        activity(replace(audio, sample_rate=22050), Detector())


async def test_audio_rates_talk_share_and_playback_latency_are_not_model_scores() -> None:
    session = synthetic_session()
    answer = session.candidate_turns()[0]
    session.turns = [
        session.turns[0],
        replace(answer, revisions=(replace(answer.current, text="ehm a meaningful answer"),)),
    ]

    class Store:
        async def metrics(self, session_id: str) -> list[dict[str, object]]:
            return [{"kind": "turn", "answer_turn_seq": 1, "answer_latency_s": 2.0}]

        async def load_turn_audio(self, session_id: str, seq: int, speaker: Speaker) -> PcmAudio:
            return PcmAudio(b"\0\0" * 16000 * (2 if speaker is Speaker.CANDIDATE else 4))

    result = {m.id: m for m in await DeliveryAnalyser(Store(), Detector).measure(session, "en")}
    assert result["speaking_rate"].value == 120
    assert result["fillers"].value == 1
    assert result["candidate_talk_share"].value == 33.3
    assert result["answer_latency"].value == 2.03
    assert result["long_pauses"].value == 1
