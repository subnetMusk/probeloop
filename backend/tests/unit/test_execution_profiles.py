"""Execution profile selection and the routing of model calls to the selected profile."""

from __future__ import annotations

from pathlib import Path

import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.ai.ports import ChatMessage, ChatRequest
from probeloop.ai.profiles import ProfiledChatModel, using_profile
from probeloop.bootstrap import with_job_profile
from probeloop.platform.jobs import Job, JobStatus, Progress
from probeloop.workspace.execution import ExecutionProfiles, ProfileUnavailableError

REQUEST = ChatRequest(instructions="x", messages=(ChatMessage("user", "y"),))


async def test_calls_go_to_the_model_of_the_profile_selected_when_they_start(
    tmp_path: Path,
) -> None:
    profiles = ExecutionProfiles(tmp_path / "profile.json", available=("local", "cloud"))
    local, cloud = FakeChatModel(["local"]), FakeChatModel(["cloud"])
    role = ProfiledChatModel({"local": local, "cloud": cloud}, lambda: profiles.current)
    assert (await role.complete(REQUEST)).text == "local"
    await profiles.select("cloud")
    assert "".join([c.text async for c in role.stream(REQUEST)]) == "cloud"
    assert (len(local.requests), len(cloud.requests)) == (1, 1)
    assert role.model_refs() == {"local": "fake:scripted", "cloud": "fake:scripted"}


async def test_the_selection_persists_and_falls_back_when_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    assert ExecutionProfiles(path, available=("local", "cloud")).current == "local"
    await ExecutionProfiles(path, available=("local", "cloud")).select("cloud")
    assert ExecutionProfiles(path, available=("local", "cloud")).current == "cloud"
    # The API key was removed after the selection: the local profile applies.
    without_cloud = ExecutionProfiles(path, available=("local",))
    assert without_cloud.current == "local"
    with pytest.raises(ProfileUnavailableError):
        await without_cloud.select("cloud")


def test_an_unreadable_selection_means_local(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text("{not json", encoding="utf-8")
    assert ExecutionProfiles(path, available=("local", "cloud")).current == "local"
    path.write_text('{"profile": "elsewhere"}', encoding="utf-8")
    assert ExecutionProfiles(path, available=("local", "cloud")).current == "local"


async def test_a_scope_selects_the_profile_of_the_calls_made_inside(tmp_path: Path) -> None:
    profiles = ExecutionProfiles(tmp_path / "profile.json", available=("local", "cloud"))
    local, cloud = FakeChatModel(["local"]), FakeChatModel(["cloud"])
    role = ProfiledChatModel({"local": local, "cloud": cloud}, lambda: profiles.current)
    with using_profile("cloud"):
        assert (await role.complete(REQUEST)).text == "cloud"
        with using_profile(None):  # keeps the enclosing choice
            assert role.model_ref == "fake:scripted"
            assert (await role.complete(REQUEST)).text == "cloud"
    assert (await role.complete(REQUEST)).text == "local"
    with pytest.raises(RuntimeError), using_profile("cloud"):
        raise RuntimeError
    assert (await role.complete(REQUEST)).text == "local"  # reset after an exception
    assert role.pinned("cloud") is cloud


async def test_jobs_run_on_the_profile_of_their_payload(tmp_path: Path) -> None:
    profiles = ExecutionProfiles(tmp_path / "profile.json", available=("local", "cloud"))
    local, cloud = FakeChatModel(["local"]), FakeChatModel(["cloud"])
    role = ProfiledChatModel({"local": local, "cloud": cloud}, lambda: profiles.current)

    async def handler(job: Job, progress: Progress) -> dict[str, str]:
        return {"text": (await role.complete(REQUEST)).text}

    async def quiet(fraction: float, message: str | None) -> None:
        pass

    run = with_job_profile(handler)
    running = JobStatus.RUNNING
    job = Job("j", "k", "s", running, created_at=0, payload={"execution": "cloud"})
    assert await run(job, quiet) == {"text": "cloud"}
    legacy = Job("j2", "k", "s", running, created_at=0, payload={})
    assert await run(legacy, quiet) == {"text": "local"}
