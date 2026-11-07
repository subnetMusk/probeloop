"""Latency and quality figures of one spoken answer and the interviewer's reply to it.

Times are seconds from the moment the server received "end of answer", on a monotonic clock.
The browser measures the full path (click to start of playback) itself; these figures split the
server's share into its steps. Nothing here contains audio or text.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class TurnMetrics:
    answer_turn_seq: int
    answer_audio_s: float
    stt_engine: str
    stt_segments: int
    stt_dropped_segments: int  # rejected by the hallucination filters
    stt_failed_segments: int
    stt_finalize_s: float  # until the final transcript
    llm_first_text_s: float | None  # until the first text of the interviewer's reply
    move_recorded_s: float | None  # until the reply was complete
    tts_voice: str
    tts_first_audio_s: float | None  # until the first sentence was ready to send
    tts_sentences: int
    tts_failed_sentences: int

    def as_record(self) -> dict[str, object]:
        return {"kind": "turn", **asdict(self)}
