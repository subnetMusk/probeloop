"""Exercise the real classifier through an isolated running app with scripted LLMs.

Requires LLM_FAKE=true, an installed Laya model, and a disposable data directory. It refuses
non-scripted model roles. No primary interview data or account settings should be used.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

import httpx
from websockets.asyncio.client import connect


async def smoke(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=url, timeout=30) as client:

        async def request(method: str, path: str, body: object | None = None) -> Any:
            response = await client.request(method, path, json=body)
            response.raise_for_status()
            return response.json()

        view = await request("GET", "/api/settings/execution")
        if not all(
            profile["models"][role].startswith("fake:")
            for profile in view["profiles"]
            for role in ("interviewer", "analysis", "evaluation")
        ):
            raise ValueError("this smoke check requires an isolated scripted application")
        for _ in range(120):
            view = await request("GET", "/api/settings/execution")
            role = next(role for role in view["tools"] if role["id"] == "limits")
            option = next(option for option in role["options"] if option["id"] == "laya")
            if option["available"]:
                break
            await asyncio.sleep(1)
        else:
            raise RuntimeError("classifier did not become available")
        await request("PUT", "/api/settings/execution", {"tools": {"limits": "laya"}})
        document = await request(
            "POST",
            "/api/documents/text",
            {
                "kind": "cv",
                "title": "Synthetic CV",
                "text": (
                    "Synthetic candidate. I maintain pumps and compare pressure measurements "
                    "before and after repairs."
                ),
            },
        )
        preparation = await request(
            "POST", "/api/preparations", {"job_mode": "none", "cv_id": document["id"]}
        )
        preparation_id = preparation["id"]
        for _ in range(60):
            preparation = await request("GET", f"/api/preparations/{preparation_id}")
            if preparation["status"] == "review":
                break
            await asyncio.sleep(0.5)
        else:
            raise RuntimeError("synthetic preparation did not finish")
        await request(
            "PUT",
            f"/api/preparations/{preparation_id}/role-profile",
            {**preparation["role_profile"], "confirmed": True},
        )
        snapshot = await request("POST", f"/api/preparations/{preparation_id}/approve")
        session = await request(
            "POST",
            "/api/sessions",
            {
                "interview_type": "technical",
                "language": "it",
                "modality": "text",
                "snapshot_id": snapshot["id"],
                "duration_minutes": 5,
            },
        )
        session_id = session["id"]
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
        async with connect(f"{ws_url}/ws/sessions/{session_id}") as ws:

            async def send(kind: str, **fields: object) -> None:
                await ws.send(json.dumps({"type": kind, **fields}))

            async def until(kind: str) -> dict[str, Any]:
                async with asyncio.timeout(30):
                    async for raw in ws:
                        message = json.loads(raw)
                        if message["type"] == "error":
                            raise RuntimeError(message)
                        if message["type"] == kind:
                            return message
                raise RuntimeError("application socket closed")

            await send("session.join", last_seq=0)
            await send("session.start")
            await until("interviewer.move.completed")
            locked = await request("GET", "/api/settings/execution")
            assert locked["locked"]
            refused = await client.put(
                "/api/settings/execution", json={"tools": {"analysis": "cloud"}}
            )
            assert refused.status_code == 409
            await send("playback.finished")
            await send("turn.start")
            started = time.perf_counter()
            await send(
                "turn.end",
                text=(
                    "Ho confrontato i dati. Non ricordo i valori esatti prima e dopo l'intervento."
                ),
            )
            await until("interviewer.move.completed")
            elapsed = time.perf_counter() - started
            recorded = await request("GET", f"/api/sessions/{session_id}")
            last = recorded["turns"][-1]
            assert last["intent"]["answer_limit"] == "stated_limit"
            await send("session.end")
            await until("session.ended")
        for _ in range(30):
            response = await client.get("/api/data/export")
            if response.status_code != 409:
                response.raise_for_status()
                break
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("disposable application did not become idle")
        tables = response.json()["tables"]
        turn = next(
            row
            for row in tables["turns"]
            if row["session_id"] == session_id and row["seq"] == last["seq"]
        )
        prompt_ref = turn["move"]["prompt_ref"]
        assert "laya-stated-limits-v1@" in prompt_ref
        return {
            "session_id": session_id,
            "classifier_used": True,
            "tools_locked_during_interview": True,
            "move_ms_with_scripted_llm": round(elapsed * 1000, 1),
            "prompt_ref": prompt_ref,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8003")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(smoke(args.url)), indent=2))


if __name__ == "__main__":
    main()
