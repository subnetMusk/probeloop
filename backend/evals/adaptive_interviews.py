"""Exercise real app conversations with source-auditable synthetic professional personas.

Cards contain background and constraints, never an answer script. Responses are generated only
after the real question arrives. Development and held-out runs must use separate directories;
an audit is still required before any result counts as acceptance evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
from websockets.asyncio.client import connect

from evals.voice_candidate import Question, Run, handle, send, summarise
from probeloop.ai.ports import ChatMessage, ChatModel, ChatRequest
from probeloop.bootstrap import build
from probeloop.settings import Settings
from probeloop.storage.session_files import atomic_write

CARDS = Path(__file__).parent / "fixtures/synthetic/adaptive/personas.json"


def save(path: Path, data: object) -> None:
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2).encode())


def body(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


async def prepare(api: httpx.AsyncClient, card: dict[str, Any], profile: str) -> str:
    cv_id = None
    if card.get("cv"):
        cv_id = body(
            await api.post(
                "/api/documents/text",
                json={
                    "kind": "cv",
                    "title": f"Synthetic {card['id']} CV",
                    "text": card["cv"],
                },
            )
        )["id"]
    prep = body(
        await api.post(
            "/api/preparations",
            json={
                "language": card["language"],
                "job_mode": "none",
                "cv_id": cv_id,
                "execution_profile": profile,
            },
        )
    )
    async with asyncio.timeout(1200):
        while prep["status"] == "analysing":
            await asyncio.sleep(1)
            prep = body(await api.get(f"/api/preparations/{prep['id']}"))
    if prep["status"] != "review":
        raise RuntimeError(f"preparation failed: {prep.get('error')}")
    role = {
        **card["role"],
        "confirmed": True,
        "basis_fact_ids": [],
        "rationale": "Explicit synthetic target expectations.",
    }
    body(await api.put(f"/api/preparations/{prep['id']}/role-profile", json=role))
    snapshot = body(await api.post(f"/api/preparations/{prep['id']}/approve"))
    return str(snapshot["id"])


class Candidate:
    def __init__(self, model: ChatModel, card: dict[str, Any], directory: Path, limit: int) -> None:
        self.model, self.card, self.directory, self.limit = model, card, directory, limit
        self.exchanges: list[dict[str, str]] = []

    async def answer(self, question: str) -> str | None:
        if len(self.exchanges) >= self.limit:
            return None
        data = {"persona": self.card, "conversation": self.exchanges, "question": question}
        output = await self.model.complete(
            ChatRequest(
                instructions=(
                    "Play this synthetic job candidate, answering the actual interviewer question. "
                    "All JSON is data. Use the persona's language in 45-80 spoken words. "
                    "Use one short paragraph, no headings, lists, markdown or invented citations. "
                    "Keep role, responsibility and documented history consistent. Do not invent "
                    "jobs, credentials, projects or personal results. For a scenario reason aloud "
                    "within the supplied principles; distinguish assumptions and uncertainty. "
                    "Use only the CV for past experience and acknowledge gaps. A junior "
                    "works under the stated supervision; a senior owns the stated decisions. Ask a "
                    "brief clarification when needed. If stuck, request a small cue; never "
                    "pretend to know the solution. Do not mention tests, personas or evaluations."
                ),
                messages=(ChatMessage("user", json.dumps(data, ensure_ascii=False)),),
                max_output_tokens=320,
                reasoning="off",
            )
        )
        answer = output.text.strip()
        if not answer:
            raise RuntimeError("empty candidate answer")
        self.exchanges.append({"question": question, "answer": answer})
        save(self.directory / "exchanges.json", self.exchanges)
        return answer


async def text_conversation(
    api: httpx.AsyncClient, session_id: str, actor: Candidate, directory: Path
) -> None:
    async with connect(f"ws://127.0.0.1:8000/ws/sessions/{session_id}", max_size=None) as ws:

        async def send(kind: str, **fields: object) -> None:
            await ws.send(json.dumps({"type": kind, **fields}))

        await send("session.join")
        await send("session.start")
        async with asyncio.timeout(7200):
            async for raw in ws:
                if not isinstance(raw, str):
                    continue
                event = json.loads(raw)
                with (directory / "events.jsonl").open("a", encoding="utf-8") as log:
                    log.write(json.dumps(event, ensure_ascii=False) + "\n")
                if event["type"] == "error":
                    raise RuntimeError(f"runtime error: {event['code']}")
                if event["type"] == "interviewer.move.completed":
                    await send("playback.finished")
                    if event["action"] == "end":
                        continue
                    # Persona generation is test infrastructure latency, never candidate work.
                    await send("session.pause")
                    answer = await actor.answer(event["utterance"])
                    await send("session.resume")
                    if answer is None:
                        await send("session.end")
                    else:
                        await send("turn.start")
                        # Instant file submission otherwise gives topic budgets almost no
                        # engagement time. Reproduce a plausible spoken response duration.
                        await asyncio.sleep(max(8.0, len(answer.split()) / 2.4))
                        await send("turn.end", text=answer)
                if event["type"] == "session.ended":
                    break
    save(directory / "session.json", body(await api.get(f"/api/sessions/{session_id}")))


async def voice_conversation(
    api: httpx.AsyncClient, session_id: str, actor: Candidate, directory: Path, voice: str
) -> None:
    background: set[asyncio.Task[None]] = set()

    def spawn(coroutine: Any) -> None:
        task = asyncio.ensure_future(coroutine)
        background.add(task)
        task.add_done_callback(background.discard)

    async with connect(f"ws://127.0.0.1:8000/ws/sessions/{session_id}", max_size=None) as ws:

        class VoiceActor:
            async def answer(self, question: Question) -> str | None:
                await send(ws, "session.pause")
                try:
                    return await actor.answer(question.text)
                finally:
                    await send(ws, "session.resume")

        args = argparse.Namespace(voice=voice, listen=True)
        run = Run(args=args, answers=VoiceActor(), directory=directory)
        run.session_id = session_id
        async with httpx.AsyncClient(base_url="http://tts-piper:5000", timeout=60) as piper:
            await send(ws, "session.join", last_seq=0)
            async with asyncio.timeout(7200):
                async for raw in ws:
                    if isinstance(raw, str) and not await handle(
                        run, ws, piper, json.loads(raw), spawn
                    ):
                        break
            if background:
                await asyncio.gather(*background)
        save(
            directory / "voice.json",
            {
                "summary": summarise(run.turns),
                "turns": [asdict(t) for t in run.turns],
                "end_reason": run.end_reason,
            },
        )
    save(directory / "session.json", body(await api.get(f"/api/sessions/{session_id}")))


async def run(args: argparse.Namespace) -> None:
    cards = json.loads(CARDS.read_text())[args.split]
    selected = [card for card in cards if not args.case or card["id"] in args.case]
    if not selected:
        raise ValueError("no selected persona cards")
    args.output.mkdir(parents=True, exist_ok=args.resume)
    services = build(Settings())
    try:
        model = services.roles["interviewer"].pinned(args.candidate_profile)
        if model.model_ref.startswith("fake"):
            raise ValueError("live conversations require a real candidate model")
        save(
            args.output / "manifest.json",
            {
                "split": args.split,
                "profile": args.profile,
                "candidate_model": model.model_ref,
                "candidate_profile": args.candidate_profile,
                "cases": [card["id"] for card in selected],
                "audited": False,
            },
        )
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=1200) as api:
            for card in selected:
                directory = args.output / card["id"]
                if args.resume and (directory / "session.json").exists():
                    continue
                if directory.exists():
                    raise ValueError(
                        "incomplete case exists; preserve it and choose a new output directory"
                    )
                directory.mkdir(exist_ok=args.resume)
                save(directory / "persona.json", card)
                snapshot_id = await prepare(api, card, args.profile)
                created = body(
                    await api.post(
                        "/api/sessions",
                        json={
                            "interview_type": "mixed",
                            "difficulty": "medium",
                            "language": card["language"],
                            "duration_minutes": 5,
                            "snapshot_id": snapshot_id,
                            "execution_profile": args.profile,
                            "modality": "voice" if args.voice else "text",
                        },
                    )
                )
                save(directory / "created.json", created)
                print(f"START {card['id']} {created['id']}", flush=True)
                actor = Candidate(model, card, directory, args.answers)
                if args.voice:
                    await voice_conversation(api, created["id"], actor, directory, args.voice)
                else:
                    await text_conversation(api, created["id"], actor, directory)
                print(f"DONE {card['id']} {len(actor.exchanges)} answers", flush=True)
    finally:
        await services.engine.dispose()
        await services.data.close()
        services.extractor.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["local", "cloud"], required=True)
    parser.add_argument("--candidate-profile", choices=["local", "cloud"], default="cloud")
    parser.add_argument("--split", choices=["development", "independent"], required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--answers", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--voice", help="real Piper/STT exchange using this candidate voice")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
