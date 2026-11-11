"""Live download/reload check against an isolated scripted app with an empty models volume.

Refuses production model roles and an already installed classifier. Pair with limits_smoke.py
afterwards to verify a complete synthetic adaptive turn. Never run against personal data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

import httpx


async def smoke(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=url, timeout=30) as client:

        async def get(path: str) -> Any:
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

        execution = await get("/api/settings/execution")
        if not all(
            profile["models"][role].startswith("fake:")
            for profile in execution["profiles"]
            for role in ("interviewer", "analysis", "evaluation")
        ):
            raise ValueError("use an isolated scripted application, never the personal runtime")
        option = next(role for role in execution["tools"] if role["id"] == "limits")["options"][-1]
        if option["id"] != "laya" or option["available"]:
            raise ValueError("this check requires a missing classifier in an empty models volume")
        started = time.perf_counter()
        response = await client.post("/api/installation/models/laya", json={})
        response.raise_for_status()
        job_id = response.json()["id"]
        for _ in range(900):
            job = await get(f"/api/jobs/{job_id}")
            if job["status"] == "failed":
                raise RuntimeError(job["error"])
            if job["status"] == "succeeded":
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError("model download did not complete")
        installed_s = time.perf_counter() - started
        for _ in range(600):
            execution = await get("/api/settings/execution")
            option = next(role for role in execution["tools"] if role["id"] == "limits")["options"][
                -1
            ]
            if option["available"]:
                break
            await asyncio.sleep(1)
        else:
            raise TimeoutError("installed classifier did not become available without restart")
        return {
            "job": job_id,
            "download_and_verification_s": round(installed_s, 2),
            "ready_s": round(time.perf_counter() - started, 2),
            "model_ref": option["model_ref"],
            "ready_without_restart": True,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(smoke(args.url)), indent=2))
