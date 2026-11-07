from __future__ import annotations

import random

import pytest

from probeloop.speech.sentences import SentenceSplitter


def split(text: str, chunk: int | None = None, max_chars: int = 250) -> list[str]:
    splitter = SentenceSplitter(max_chars=max_chars)
    pieces = [text] if chunk is None else [text[i : i + chunk] for i in range(0, len(text), chunk)]
    out: list[str] = []
    for piece in pieces:
        out += splitter.feed(piece)
    return out + splitter.flush()


CASES = [
    ("Buongiorno. Mi parli di lei?", ["Buongiorno.", "Mi parli di lei?"]),
    (
        "Bene! Passiamo oltre. Come ha gestito il rilascio?",
        ["Bene!", "Passiamo oltre.", "Come ha gestito il rilascio?"],
    ),
    (
        "Ha parlato con il Dott. Rossi del progetto? Bene.",
        ["Ha parlato con il Dott. Rossi del progetto?", "Bene."],
    ),
    (
        "Usa una coda, es. Kafka o RabbitMQ? Mi spieghi.",
        ["Usa una coda, es. Kafka o RabbitMQ?", "Mi spieghi."],
    ),
    ("Ho letto il CV di A. Bianchi. Iniziamo?", ["Ho letto il CV di A. Bianchi.", "Iniziamo?"]),
    ("La versione 3.5 era stabile. Poi?", ["La versione 3.5 era stabile.", "Poi?"]),
    ("Nel 2020. Poi nel 2021.", ["Nel 2020.", "Poi nel 2021."]),
    (
        "Erano tre... forse quattro persone. Giusto?",
        ["Erano tre... forse quattro persone.", "Giusto?"],
    ),
    ("Partiamo da qui… Mi racconti.", ["Partiamo da qui…", "Mi racconti."]),
    ("Ha detto «basta». Perché?", ["Ha detto «basta».", "Perché?"]),
    ('Lei ha scritto "funziona." Ne è sicuro?', ['Lei ha scritto "funziona."', "Ne è sicuro?"]),
    ("Capito.\nProssima domanda?", ["Capito.", "Prossima domanda?"]),
    ("Good morning, Mr. Smith. Shall we start?", ["Good morning, Mr. Smith.", "Shall we start?"]),
    ("Ultima frase senza punto", ["Ultima frase senza punto"]),
    ("  ", []),
]


@pytest.mark.parametrize("chunk", [None, 1, 3], ids=["whole", "by-char", "by-3"])
@pytest.mark.parametrize(("text", "expected"), CASES)
def test_sentences(text: str, expected: list[str], chunk: int | None) -> None:
    assert split(text, chunk) == expected


def test_a_sentence_ends_only_once_the_next_one_has_started() -> None:
    splitter = SentenceSplitter()
    assert splitter.feed("Buongiorno.") == []
    assert splitter.feed(" ") == []
    assert splitter.feed("M") == ["Buongiorno."]
    assert splitter.flush() == ["M"]


def test_flush_returns_the_last_sentence_once() -> None:
    splitter = SentenceSplitter()
    assert splitter.feed("Grazie, abbiamo finito.") == []
    assert splitter.flush() == ["Grazie, abbiamo finito."]
    assert splitter.flush() == []


def test_fragments_without_words_are_not_spoken() -> None:
    assert split("Bene. … Allora?") == ["Bene.", "Allora?"]
    assert split("— ?") == []


def test_a_long_sentence_is_cut_at_its_last_comma() -> None:
    clause = "abbiamo migrato i servizi uno alla volta"
    text = ", ".join([clause] * 8) + "."
    sentences = split(text, chunk=5, max_chars=100)
    assert len(sentences) > 1
    assert all(len(s) <= 100 for s in sentences)
    assert all(s.endswith((",", ".")) for s in sentences)
    assert " ".join(sentences) == text


def test_without_commas_a_long_sentence_is_cut_at_a_space() -> None:
    text = " ".join(["parola"] * 60)
    sentences = split(text, max_chars=50)
    assert all(len(s) <= 50 for s in sentences)
    assert " ".join(sentences) == text


def test_random_chunking_gives_the_same_sentences() -> None:
    text = " ".join(t for t, _ in CASES)
    reference = split(text)
    rng = random.Random(3)
    for _ in range(20):
        splitter = SentenceSplitter()
        out: list[str] = []
        i = 0
        while i < len(text):
            size = rng.randint(1, 12)
            out += splitter.feed(text[i : i + size])
            i += size
        assert out + splitter.flush() == reference


def test_max_chars_must_allow_a_sentence() -> None:
    with pytest.raises(ValueError, match="too small"):
        SentenceSplitter(max_chars=5)


QUESTION = (
    "Signor Bianchi, durante il confronto tra il solver e la pianificazione manuale, "
    "quali metriche ha usato per decidere che le rotte erano affidabili?"
)


@pytest.mark.parametrize("chunk", [None, 1, 4])
def test_the_first_chunk_can_end_at_a_clause(chunk: int | None) -> None:
    splitter = SentenceSplitter(first_clause_chars=40)
    pieces = (
        [QUESTION]
        if chunk is None
        else [QUESTION[i : i + chunk] for i in range(0, len(QUESTION), chunk)]
    )
    out: list[str] = []
    for piece in pieces:
        out += splitter.feed(piece)
    out += splitter.flush()
    assert out == [
        "Signor Bianchi, durante il confronto tra il solver e la pianificazione manuale,",
        "quali metriche ha usato per decidere che le rotte erano affidabili?",
    ]


def test_only_the_first_chunk_is_cut_at_a_clause() -> None:
    splitter = SentenceSplitter(first_clause_chars=10)
    text = "Bene, partiamo. Mi racconti, con calma e nel dettaglio, il suo ultimo progetto? "
    assert splitter.feed(text + "X") == [
        "Bene, partiamo.",
        "Mi racconti, con calma e nel dettaglio, il suo ultimo progetto?",
    ]


def test_a_short_first_sentence_is_not_cut() -> None:
    assert split("Grazie, molto chiaro. Passiamo oltre.") == [
        "Grazie, molto chiaro.",
        "Passiamo oltre.",
    ]
