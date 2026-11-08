"""Create a complete synthetic report export for visual regression review."""

from __future__ import annotations

import argparse
import asyncio
import tempfile
from pathlib import Path

from tests.assessment.support import synthetic_session

from probeloop.bootstrap import build
from probeloop.settings import Settings


async def run(output: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        container = build(Settings(data_dir=Path(directory), llm_fake=True))
        await container.startup()
        try:
            session = synthetic_session()
            await container.store.save(session)
            job = await container.assessment.submit_interview(session.id, "en")
            await container.jobs.wait_idle()
            finished = await container.jobs.get(job.id)
            assert finished is not None
            assert finished.result, finished
            report = await container.assessment.report(str(finished.result["report_id"]))
            output.parent.mkdir(parents=True, exist_ok=True)
            for format in ("md", "json", "pdf"):
                content = await asyncio.to_thread(container.export_report, report, format)
                await asyncio.to_thread(output.with_suffix("." + format).write_bytes, content)
        finally:
            await container.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args().output))
