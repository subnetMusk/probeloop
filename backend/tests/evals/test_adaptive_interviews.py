import json
from pathlib import Path

import httpx
from evals.adaptive_interviews import CARDS, Candidate, prepare

from probeloop.ai.fake import FakeChatModel


def test_matrix_separates_development_and_independent_professions() -> None:
    cards = json.loads(CARDS.read_text())
    assert len(cards["development"]) == 8
    assert len(cards["independent"]) == 4
    for split, expected in (("development", 4), ("independent", 2)):
        assert len({c["role"]["profession"] for c in cards[split]}) >= expected
        assert sum(c["language"] == "en" for c in cards[split]) == len(cards[split]) // 2
        assert all(c["sources"] and "answers" not in c for c in cards[split])


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
