"""Contract of the Jev stated-limit reader against a scripted TypeSafe endpoint."""

from __future__ import annotations

import json
import logging
import stat
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

from probeloop.interview.application.ports import LimitReaderUnavailable
from probeloop.interview.infrastructure.jev_limits import (
    KEY_MISSING,
    KEY_REJECTED,
    MODEL,
    UNREACHABLE,
    JevKeyFile,
    JevStatedLimitReader,
)

KEY = "synthetic-test-key"
QUESTION = "Ha mai condotto una trattativa con un fornitore?"
ANSWER = "No, non ho mai condotto io una trattativa. Ho preparato i confronti fra le offerte."


async def no_wait(seconds: float) -> None:
    pass


def reader(tmp_path: Path, handler: Any, *, key: str | None = KEY) -> JevStatedLimitReader:
    keys = JevKeyFile(tmp_path / "typesafe")
    if key is not None:
        keys.save(key)
    return JevStatedLimitReader(keys, transport=httpx.MockTransport(handler), sleep=no_wait)


def scores(*values: float) -> dict[str, Any]:
    return {
        "model": MODEL,
        "answers": {f"s{i}": {"type": "noul", "noul": v} for i, v in enumerate(values)},
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }


async def test_one_request_per_answer_returns_the_sentences_over_the_threshold(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=scores(0.93, 0.04))

    limits = reader(tmp_path, handler)
    reading = await limits.read(QUESTION, ANSWER)
    assert reading.quotes == ("No, non ho mai condotto io una trattativa.",)
    assert reading.source_ref == f"typesafe:{MODEL}:limits.v2:threshold=0.5"
    (request,) = requests
    assert request.url == "https://api.typesafe.ai/v1/systemone"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert body["model"] == "jev-1.14.0"  # a pinned version, never the moving alias
    assert body["state"] == {
        "interviewer_question": QUESTION,
        "candidate_answer_sentences": [
            "No, non ho mai condotto io una trattativa.",
            "Ho preparato i confronti fra le offerte.",
        ],
    }
    assert list(body["questions"]) == ["s0", "s1"]
    assert {q["type"] for q in body["questions"].values()} == {"noul"}
    assert "candidate_answer_sentences[1]" in body["questions"]["s1"]["instructions"]
    assert set(body["questions"]["s0"]["criteria"]) == {"true", "false"}
    await limits.aclose()


async def test_the_reference_records_the_version_that_answered(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**scores(0.1, 0.2), "model": "jev-1.14.1"})

    reading = await reader(tmp_path, handler).read(QUESTION, ANSWER)
    assert reading.quotes == ()
    assert reading.source_ref.startswith("typesafe:jev-1.14.1:")


async def test_an_empty_answer_needs_no_request(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    assert (await reader(tmp_path, handler, key=None).read(QUESTION, "  ")).quotes == ()


async def test_transient_overload_is_retried_then_pauses(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(529) if calls < 3 else httpx.Response(200, json=scores(0.0, 0.9))

    assert (await reader(tmp_path, handler).read(QUESTION, ANSWER)).quotes == (
        "Ho preparato i confronti fra le offerte.",
    )
    assert calls == 3

    def overloaded(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "30"})

    with pytest.raises(LimitReaderUnavailable, match=UNREACHABLE):
        await reader(tmp_path / "b", overloaded).read(QUESTION, ANSWER)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(401, json={"detail": "bad key"}), KEY_REJECTED),
        (httpx.Response(422, json={"detail": "invalid"}), "Jev could not read the answer"),
        (httpx.Response(200, json={"answers": {"s0": {"noul": 0.9}}}), "could not read"),
        (httpx.Response(200, json=scores(1.5, 0.0)), "could not read"),
        (httpx.Response(200, text="not json"), "could not read"),
    ],
)
async def test_failures_make_the_reader_unavailable(
    tmp_path: Path, response: httpx.Response, message: str
) -> None:
    with pytest.raises(LimitReaderUnavailable, match=message):
        await reader(tmp_path, lambda request: response).read(QUESTION, ANSWER)


async def test_a_network_failure_never_reports_the_key(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    caplog.set_level(logging.DEBUG)
    with pytest.raises(LimitReaderUnavailable) as raised:
        await reader(tmp_path, handler).read(QUESTION, ANSWER)
    assert str(raised.value) == UNREACHABLE
    assert raised.value.__cause__ is None
    assert KEY not in caplog.text
    assert QUESTION not in caplog.text
    assert "trattativa" not in caplog.text


async def test_check_and_verify_list_the_models_with_the_key(tmp_path: Path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        assert request.url.path == "/v1/models"
        if request.headers["authorization"] == f"Bearer {KEY}":
            return httpx.Response(200, json={"models": []})
        return httpx.Response(401)

    limits = reader(tmp_path, handler)
    await limits.check()
    assert await limits.verify("another-key") == "key_rejected"
    assert seen == [f"Bearer {KEY}", "Bearer another-key"]
    with pytest.raises(LimitReaderUnavailable, match=KEY_MISSING):
        await reader(tmp_path / "none", handler, key=None).check()

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    assert await reader(tmp_path / "down", down).verify(KEY) == "unreachable"


def test_the_key_file_is_private_and_removable(tmp_path: Path) -> None:
    keys = JevKeyFile(tmp_path / "typesafe")
    assert not keys.configured
    keys.save(KEY)
    assert keys.read() == KEY
    assert keys.configured
    if sys.platform != "win32":
        mode = stat.S_IMODE((tmp_path / "typesafe" / "api-key").stat().st_mode)
        assert mode == 0o600
    keys.clear()
    assert keys.read() is None
    keys.clear()  # removing a missing key is not an error
