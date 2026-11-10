import json
import time
from pathlib import Path

import httpx
import pytest
from evals.adaptive_interviews import CARDS, Candidate, prepare, stamped

from evals import adaptive_interviews
from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import ChatRequest, ChatResult, LlmError


def test_logged_events_carry_the_client_receive_time() -> None:
    record = stamped({"type": "interviewer.text.delta", "text": "Hello"}, time.monotonic() - 2)
    assert record["type"] == "interviewer.text.delta"
    assert record["text"] == "Hello"
    assert 2 <= record["_t"] < 10


def test_matrix_separates_development_and_independent_professions() -> None:
    cards = json.loads(CARDS.read_text())
    assert len(cards["development"]) == 8
    assert len(cards["independent"]) == 4
    for split, expected in (("development", 4), ("independent", 2)):
        assert len({c["role"]["profession"] for c in cards[split]}) >= expected
        assert sum(c["language"] == "en" for c in cards[split]) == len(cards[split]) // 2
        assert all(c["sources"] and "answers" not in c for c in cards[split])
        assert all(c["style"] and c["history"] for c in cards[split])


async def test_answers_are_generated_from_the_actual_question_and_keep_history(
    tmp_path: Path,
) -> None:
    model = FakeChatModel(["I would check the definition.", "I would ask my supervisor."])
    actor = Candidate(model, {"id": "synthetic", "language": "en"}, tmp_path, 2)
    await actor.answer("Which definition?")
    await actor.answer("Who would help you?")
    assert await actor.answer("Another?") is None
    data = json.loads(model.requests[1].messages[0].content)
    assert data["question"] == "Who would help you?"
    assert data["conversation"][0]["answer"] == "I would check the definition."


async def test_a_transient_actor_failure_is_retried_while_the_session_is_paused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(adaptive_interviews, "ACTOR_RETRY_S", 0.0)
    model = FakeChatModel(["I would check the definition."])
    complete = model.complete
    failures = [LlmError("provider hiccup")]

    async def flaky(request: ChatRequest) -> ChatResult:
        if failures:
            raise failures.pop()
        return await complete(request)

    monkeypatch.setattr(model, "complete", flaky)
    actor = Candidate(model, {"id": "synthetic", "language": "en"}, tmp_path, 1)
    assert await actor.answer("Which definition?") == "I would check the definition."


async def test_the_actor_receives_its_belief_but_never_the_audit_correction(
    tmp_path: Path,
) -> None:
    card = next(
        c for c in json.loads(CARDS.read_text())["development"] if c["id"] == "software-senior"
    )
    model = FakeChatModel(["Risposta."])
    await Candidate(model, card, tmp_path, 1).answer("Domanda?")
    sent = model.requests[0].messages[0].content
    assert card["error"]["belief"] in sent
    assert card["error"]["correct"] not in sent
    assert "sources" not in json.loads(sent)["persona"]
    assert "mistaken belief" in model.requests[0].instructions


async def test_offers_and_resources_are_uploaded_with_their_document_kinds() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else {}
        seen.append((request.url.path, payload))
        if request.url.path == "/api/documents/text":
            return httpx.Response(201, json={"id": payload["kind"]})
        if request.url.path == "/api/preparations":
            return httpx.Response(202, json={"id": "prep", "status": "review"})
        return httpx.Response(200, json={"id": "snapshot"})

    cards = json.loads(CARDS.read_text())["development"]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://app"
    ) as api:
        for card_id in ("software-junior", "software-senior"):
            await prepare(api, next(c for c in cards if c["id"] == card_id), "cloud")
    preparations = [p for path, p in seen if path == "/api/preparations"]
    assert preparations[0]["job_mode"] == "offer"
    assert preparations[0]["job_offer_id"] == "job_offer"
    assert preparations[1]["job_mode"] == "none"
    assert preparations[1]["resources"][0]["document_id"] == "resource"


async def test_document_free_runtime_setup_confirms_role_and_profile() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else {}
        seen.append((request.url.path, payload))
        if request.url.path == "/api/preparations":
            return httpx.Response(202, json={"id": "prep", "status": "review"})
        return httpx.Response(200, json={"id": "snapshot"})

    card = json.loads(CARDS.read_text())["development"][2]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://app"
    ) as api:
        assert await prepare(api, card, "local") == "snapshot"
    assert seen[0][1]["execution_profile"] == "local"
    assert seen[1][1]["confirmed"] is True
    assert seen[1][1]["seniority"] == "Junior"
