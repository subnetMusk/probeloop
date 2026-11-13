"""Contract of the Jev line classifier against a scripted TypeSafe endpoint."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest

from probeloop.context.application.ports import OfferLine, TextClassifierUnavailable
from probeloop.context.domain.model import Obligation
from probeloop.context.infrastructure.jev_classifier import MODEL, JevTextClassifier
from probeloop.platform.jev import JevKeyFile

KEY = "synthetic-test-key"
LINES = [
    OfferLine("Almeno tre anni di esperienza come sviluppatore backend.", "Requisiti"),
    OfferLine("Esperienza nel dominio dei pagamenti.", "Gradito"),
    OfferLine("Esperienza con basi dati relazionali (preferibilmente PostgreSQL).", "Requisiti"),
    OfferLine("Buoni pasto e budget formazione annuale.", "Cosa offriamo"),
]


async def no_wait(seconds: float) -> None:
    pass


def classifier(
    tmp_path: Path, handler: Any, *, key: str | None = KEY, max_questions: int = 40
) -> JevTextClassifier:
    keys = JevKeyFile(tmp_path / "typesafe")
    if key is not None:
        keys.save(key)
    return JevTextClassifier(
        keys,
        transport=httpx.MockTransport(handler),
        sleep=no_wait,
        max_questions=max_questions,
    )


def reply(scores: dict[str, float], model: str = MODEL) -> httpx.Response:
    answers = {q: {"type": "noul", "noul": v} for q, v in scores.items()}
    return httpx.Response(200, json={"model": model, "answers": answers})


async def test_obligation_needs_one_reading_alone_over_its_threshold(tmp_path: Path) -> None:
    bodies: list[dict[str, Any]] = []
    # Requirement and preference probabilities for each of the four lines.
    must = [0.9, 0.2, 0.9, 0.1]
    preferred = [0.1, 0.8, 0.7, 0.2]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/systemone"
        assert request.headers["authorization"] == f"Bearer {KEY}"
        bodies.append(json.loads(request.content))
        scores = {f"q0_{i}": v for i, v in enumerate(must)}
        scores |= {f"q1_{i}": v for i, v in enumerate(preferred)}
        return reply(scores, "jev-1.14.2")

    result = await classifier(tmp_path, handler).obligations(LINES)

    assert [r.obligation for r in result.readings] == [
        Obligation.MUST,
        Obligation.PREFERRED,
        Obligation.UNCLEAR,
        Obligation.UNCLEAR,
    ]
    assert result.readings[0].must == 0.9
    assert result.model_ref == "typesafe:jev-1.14.2:cv.obligation.v1:must=0.5:preferred=0.5"
    (body,) = bodies
    assert body["model"] == MODEL
    assert body["state"]["offer_lines"][1] == {
        "heading": "Gradito",
        "text": "Esperienza nel dominio dei pagamenti.",
    }
    assert set(body["questions"]) == {f"q{w}_{i}" for w in (0, 1) for i in range(4)}
    assert "offer_lines[2].heading" in body["questions"]["q1_2"]["instructions"]
    assert body["questions"]["q0_0"]["type"] == "noul"


async def test_long_documents_are_split_and_keep_their_order(tmp_path: Path) -> None:
    lines = [f"Riga {i}" for i in range(5)]
    states: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        batch = body["state"]["cv_lines"]
        states.append(batch)
        return reply({f"q0_{i}": int(text[-1]) / 10 for i, text in enumerate(batch)})

    result = await classifier(tmp_path, handler, max_questions=2).quantified(lines)

    assert states == [["Riga 0", "Riga 1"], ["Riga 2", "Riga 3"], ["Riga 4"]]
    assert [r.score for r in result.readings] == [0.0, 0.1, 0.2, 0.3, 0.4]
    assert result.model_ref == f"typesafe:{MODEL}:cv.quantified.v2:threshold=0.7"


async def test_line_readings_apply_the_wording_threshold(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "section heading" in json.loads(request.content)["questions"]["q0_0"]["instructions"]
        return reply({"q0_0": 0.93, "q0_1": 0.69, "q0_2": 0.7})

    result = await classifier(tmp_path, handler).headings(
        ["E S P E R I E N Z E", "Backend developer, Trasporti Digitali", "Work history"]
    )
    assert [r.positive for r in result.readings] == [True, False, True]
    assert result.model_ref == f"typesafe:{MODEL}:cv.heading.v2:threshold=0.7"


async def test_no_lines_need_no_request(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    result = await classifier(tmp_path, handler).quantified([])
    assert result.readings == ()


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(401), "rejected"),
        (httpx.Response(422, json={"detail": "invalid"}), "could not classify"),
        (reply({"q0_0": 0.9}), "could not classify"),
        (reply({"q0_0": 1.4, "q0_1": 0.1}), "could not classify"),
        (httpx.Response(200, text="not json"), "could not classify"),
        (httpx.Response(503), "unreachable"),
    ],
)
async def test_failures_make_the_classifier_unavailable(
    tmp_path: Path, response: httpx.Response, message: str
) -> None:
    with pytest.raises(TextClassifierUnavailable, match=message) as raised:
        await classifier(tmp_path, lambda request: response).headings(["Esperienze", "Python"])
    assert raised.value.__cause__ is None


async def test_a_missing_key_is_reported_before_any_request(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with pytest.raises(TextClassifierUnavailable, match="add a Jev API key"):
        await classifier(tmp_path, handler, key=None).obligations(LINES)


async def test_logs_carry_neither_the_key_nor_the_text(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    caplog.set_level(logging.DEBUG)
    with pytest.raises(TextClassifierUnavailable, match="unreachable"):
        await classifier(tmp_path, down).obligations(LINES)

    def answered(request: httpx.Request) -> httpx.Response:
        return reply({f"q{w}_{i}": 0.6 for w in (0, 1) for i in range(len(LINES))})

    await classifier(tmp_path / "ok", answered).obligations(LINES)
    assert KEY not in caplog.text
    assert "pagamenti" not in caplog.text
    assert "document classification completed" in caplog.text


async def test_v2_wordings_name_the_line_as_well_as_its_index(tmp_path: Path) -> None:
    from probeloop.context.infrastructure.jev_classifier import HEADING_V2, QUANTIFIED_V2

    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return reply({"q0_0": 0.9, "q0_1": 0.1})

    keys = JevKeyFile(tmp_path / "typesafe")
    keys.save(KEY)
    jev = JevTextClassifier(
        keys,
        transport=httpx.MockTransport(handler),
        sleep=no_wait,
        line_wordings={"quantified": QUANTIFIED_V2, "heading": HEADING_V2},
    )
    result = await jev.headings(["Formazione", "2018 Laurea triennale in Informatica"])

    assert result.model_ref == f"typesafe:{MODEL}:cv.heading.v2:threshold=0.7"
    instructions = bodies[0]["questions"]["q0_1"]["instructions"]
    assert '`cv_lines[1]` reads: "2018 Laurea triennale in Informatica"' in instructions
