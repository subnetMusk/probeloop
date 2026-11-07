"""Cuts a live audio stream into speech segments, using a voice activity detector.

A segment closes at a pause of `min_silence_s` (600 ms by default, ADR 0009), or is cut once it
reaches `max_segment_s` (15 s), so the audio left to transcribe after "end of answer" stays short.
A forced cut prefers the latest short pause inside the segment, so that words are not split.

The thresholds follow Silero VAD's own segmentation: speech starts at `threshold` and a pause
starts below `neg_threshold`; probabilities in between keep the current state.
"""

from __future__ import annotations

from dataclasses import dataclass

from probeloop.speech.audio import SAMPLE_RATE, SAMPLE_WIDTH, PcmAudio
from probeloop.speech.ports import VAD_WINDOW_SAMPLES, VoiceActivityDetector


@dataclass(frozen=True, slots=True)
class SegmenterConfig:
    threshold: float = 0.5
    neg_threshold: float = 0.35
    min_silence_s: float = 0.6  # a pause this long closes the segment
    max_segment_s: float = 15.0  # longer segments are cut
    min_speech_s: float = 0.25  # shorter bursts of speech are discarded
    pad_s: float = 0.2  # audio kept around the detected speech
    split_pause_s: float = 0.1  # a pause this long is a good place for a forced cut
    min_forced_segment_s: float = 1.0  # a forced cut never leaves a shorter segment behind

    def __post_init__(self) -> None:
        if not 0.0 < self.neg_threshold < self.threshold <= 1.0:
            raise ValueError("thresholds must satisfy 0 < neg_threshold < threshold <= 1")
        if not 0.0 <= self.pad_s < self.min_silence_s:
            raise ValueError("the padding must be shorter than the closing pause")
        if not 0.0 < self.split_pause_s < self.min_silence_s:
            raise ValueError("the split pause must be shorter than the closing pause")
        if not 0.0 < self.min_forced_segment_s < self.max_segment_s:
            raise ValueError("the minimum forced segment must be shorter than the maximum")


@dataclass(frozen=True, slots=True)
class SpeechSegment:
    index: int
    start: int  # sample offsets within the stream
    end: int
    audio: PcmAudio
    forced: bool  # cut at the maximum length, not at a pause

    @property
    def start_s(self) -> float:
        return self.start / SAMPLE_RATE

    @property
    def end_s(self) -> float:
        return self.end / SAMPLE_RATE

    @property
    def duration_s(self) -> float:
        return (self.end - self.start) / SAMPLE_RATE


def _samples(seconds: float) -> int:
    return round(seconds * SAMPLE_RATE)


class SpeechSegmenter:
    """Feeds 16 kHz PCM to the detector window by window and returns the closed segments.

    The segmenter also keeps the whole stream, which is the audio stored for the turn. It is not
    thread-safe: one caller feeds it in order.
    """

    def __init__(self, vad: VoiceActivityDetector, config: SegmenterConfig | None = None) -> None:
        self._vad = vad
        self._config = config = config or SegmenterConfig()
        self._min_silence = _samples(config.min_silence_s)
        self._max_segment = _samples(config.max_segment_s)
        self._min_speech = _samples(config.min_speech_s)
        self._pad = _samples(config.pad_s)
        self._split_pause = _samples(config.split_pause_s)
        self._min_forced = _samples(config.min_forced_segment_s)

        self._stream = bytearray()
        self._analysed = 0  # samples already passed to the detector
        self._in_speech = False
        self._segment_start = 0  # first sample of the open segment, padding included
        self._speech_start = 0  # first speech sample of the open segment
        self._pause_start: int | None = None  # start of the current pause inside the segment
        self._split_at: int | None = None  # preferred place for a forced cut
        self._previous_end = 0  # segments never overlap
        self._next_index = 0
        self._finished = False
        self.discarded = 0  # bursts of speech shorter than `min_speech_s`

    @property
    def audio(self) -> PcmAudio:
        """Everything fed so far."""
        return PcmAudio(bytes(self._stream))

    def feed(self, pcm: bytes) -> list[SpeechSegment]:
        if self._finished:
            raise RuntimeError("the segmenter has been flushed")
        if len(pcm) % SAMPLE_WIDTH:
            raise ValueError("16-bit PCM needs an even number of bytes")
        self._stream += pcm
        available = len(self._stream) // SAMPLE_WIDTH
        closed: list[SpeechSegment] = []
        view = memoryview(self._stream)
        try:
            while self._analysed + VAD_WINDOW_SAMPLES <= available:
                start = self._analysed
                end = start + VAD_WINDOW_SAMPLES
                window = bytes(view[start * SAMPLE_WIDTH : end * SAMPLE_WIDTH])
                probability = self._vad.speech_probability(window)
                self._analysed = end
                segment = self._step(start, end, probability)
                if segment is not None:
                    closed.append(segment)
        finally:
            view.release()
        return closed

    def flush(self) -> list[SpeechSegment]:
        """Close the open segment at the end of the stream. No more audio can be fed afterwards."""
        if self._finished:
            return []
        self._finished = True
        if not self._in_speech:
            return []
        total = len(self._stream) // SAMPLE_WIDTH
        speech_end = self._pause_start if self._pause_start is not None else total
        segment = self._close(speech_end, min(speech_end + self._pad, total))
        return [segment] if segment is not None else []

    # ------------------------------------------------------------------ state machine

    def _step(self, start: int, end: int, probability: float) -> SpeechSegment | None:
        config = self._config
        if not self._in_speech:
            if probability >= config.threshold:
                self._in_speech = True
                self._speech_start = start
                self._segment_start = max(start - self._pad, self._previous_end)
                self._pause_start = None
                self._split_at = None
            return None

        if probability >= config.threshold:
            self._pause_start = None
        elif probability < config.neg_threshold:
            if self._pause_start is None:
                self._pause_start = start
            pause = end - self._pause_start
            if pause >= self._min_silence:
                return self._close(self._pause_start, self._pause_start + self._pad)
            if pause >= self._split_pause:
                middle = (self._pause_start + end) // 2
                if middle - self._segment_start >= self._min_forced:
                    self._split_at = middle

        if end - self._segment_start >= self._max_segment:
            return self._cut()
        return None

    def _close(self, speech_end: int, segment_end: int) -> SpeechSegment | None:
        self._in_speech = False
        self._pause_start = None
        self._split_at = None
        speech = speech_end - self._speech_start
        if speech < self._min_speech:
            if speech > 0:  # zero after a forced cut that landed in the closing pause
                self.discarded += 1
            return None
        return self._emit(self._segment_start, segment_end, forced=False)

    def _cut(self) -> SpeechSegment:
        if self._split_at is not None:
            cut = self._split_at
        else:
            cut = self._segment_start + self._max_segment
        segment = self._emit(self._segment_start, cut, forced=True)
        self._segment_start = self._speech_start = cut
        if self._pause_start is not None and self._pause_start < cut:
            self._pause_start = cut
        self._split_at = None
        return segment

    def _emit(self, start: int, end: int, *, forced: bool) -> SpeechSegment:
        data = bytes(self._stream[start * SAMPLE_WIDTH : end * SAMPLE_WIDTH])
        segment = SpeechSegment(
            index=self._next_index, start=start, end=end, audio=PcmAudio(data), forced=forced
        )
        self._next_index += 1
        self._previous_end = end
        return segment
