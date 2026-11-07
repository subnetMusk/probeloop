"""UtteranceSynthesizer with the fake speech synthesiser."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from probeloop.speech.fake import FakeTextToSpeech
from probeloop.speech.ports import SpeechError
from probeloop.speech.synthesizer import (
    SentenceFailed,
    SpokenSentence,
    SynthesisEvent,
    SynthesizerClosedError,
    UtteranceSynthesizer,
)

VOICE = "it_IT-serena-medium"


@dataclass
class Events:
    items: list[SynthesisEvent] = field(default_factory=list)

    async def __call__(self, event: SynthesisEvent) -> None:
        self.items.append(event)


def synthesizer(tts: FakeTextToSpeech, events: Events | None = None) -> UtteranceSynthesizer:
    s = UtteranceSynthesizer(tts, VOICE, sink=events)
    s.start()
    return s


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


async def test_the_first_sentence_is_spoken_before_the_text_is_complete() -> None:
    tts = FakeTextToSpeech()
    events = Events()
    s = synthesizer(tts, events)
    for delta in ["Buongiorno e ", "benvenuto. Inizi", "amo dal suo ", "percorso?"]:
        s.push(delta)
        await settle()
    assert [text for text, _ in tts.calls] == ["Buongiorno e benvenuto."]
    assert len(events.items) == 1

    speech = await s.finish()
    assert [(x.index, x.text) for x in speech.sentences] == [
        (0, "Buongiorno e benvenuto."),
        (1, "Iniziamo dal suo percorso?"),
    ]
    assert all(voice == VOICE for _, voice in tts.calls)
    assert speech.complete
    assert speech.first_audio_s == speech.sentences[0].ready_s
    assert 0 <= speech.sentences[0].synth_s <= speech.sentences[0].ready_s
    assert speech.audio_s == pytest.approx(sum(x.audio.duration_s for x in speech.sentences))
    assert [e.index for e in events.items] == [0, 1]


async def test_a_whole_utterance_at_once() -> None:
    tts = FakeTextToSpeech()
    s = synthesizer(tts)
    s.push("Grazie, il colloquio è terminato. Buona giornata.")
    speech = await s.finish()
    assert [x.text for x in speech.sentences] == [
        "Grazie, il colloquio è terminato.",
        "Buona giornata.",
    ]
    assert speech.sentences[0].audio.sample_rate == 22_050


async def test_a_failed_call_is_retried() -> None:
    tts = FakeTextToSpeech(script=[SpeechError("busy"), None])
    s = synthesizer(tts)
    s.push("Una frase.")
    speech = await s.finish()
    assert [x.text for x in speech.sentences] == ["Una frase."]
    assert len(tts.calls) == 2


async def test_a_sentence_that_keeps_failing_is_reported_and_the_rest_is_spoken() -> None:
    tts = FakeTextToSpeech(script=[SpeechError("down"), SpeechError("down")])
    events = Events()
    s = synthesizer(tts, events)
    s.push("Prima frase. Seconda frase.")
    speech = await s.finish()
    assert [(f.index, f.text) for f in speech.failed] == [(0, "Prima frase.")]
    assert [(x.index, x.text) for x in speech.sentences] == [(1, "Seconda frase.")]
    assert not speech.complete
    assert speech.first_audio_s == speech.sentences[0].ready_s
    assert isinstance(events.items[0], SentenceFailed)
    assert isinstance(events.items[1], SpokenSentence)


async def test_cancel_drops_the_sentences_still_queued() -> None:
    tts = FakeTextToSpeech(delay_s=0.2)
    events = Events()
    s = synthesizer(tts, events)
    s.push("Uno. Due. Tre. ")
    s.push("Quattro")
    await settle()
    await s.cancel()
    assert len(tts.calls) == 1  # the first call was running; the others never started
    assert events.items == []
    with pytest.raises(SynthesizerClosedError):
        s.push("Cinque.")
    with pytest.raises(SynthesizerClosedError):
        await s.finish()


async def test_an_utterance_finishes_only_once() -> None:
    s = synthesizer(FakeTextToSpeech())
    s.push("Fine.")
    await s.finish()
    with pytest.raises(SynthesizerClosedError):
        await s.finish()
    with pytest.raises(SynthesizerClosedError):
        s.push("Altro.")


async def test_nothing_to_say_gives_an_empty_result() -> None:
    tts = FakeTextToSpeech()
    speech = await synthesizer(tts).finish()
    assert speech.sentences == ()
    assert speech.first_audio_s is None
    assert tts.calls == []


async def test_a_broken_listener_does_not_stop_the_utterance() -> None:
    async def broken(event: SynthesisEvent) -> None:
        raise RuntimeError("client gone")

    s = UtteranceSynthesizer(FakeTextToSpeech(), VOICE, sink=broken)
    s.start()
    s.push("Uno. Due.")
    speech = await s.finish()
    assert len(speech.sentences) == 2
