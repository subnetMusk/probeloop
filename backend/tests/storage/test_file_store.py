from __future__ import annotations

import json
from pathlib import Path

import pytest

from probeloop.interview.domain.model import (
    EndReason,
    InterviewerMove,
    Modality,
    MoveAction,
    MoveStatus,
    SessionStatus,
    Speaker,
)
from probeloop.speech.audio import PcmAudio, from_wav
from probeloop.storage.file_store import FileSessionStore, from_dict, to_dict
from tests.conftest import make_session
from tests.speech_audio import tone

SESSION_ID = "a" * 32


def played_session():  # type: ignore[no-untyped-def]
    s = make_session(session_id=SESSION_ID)
    s.start(10)
    s.record_move(
        InterviewerMove(
            MoveAction.NEW_TOPIC, "t2", "Progetto?", ("t1",), model_ref="m", prompt_ref="p@v1"
        ),
        11,
    )
    s.finish_speaking(12)
    s.start_answer(13)
    s.finish_answer(14)
    s.record_answer("Un servizio di routing.", 15)
    s.pause(
        16,
        partial_move=InterviewerMove(
            MoveAction.FOLLOW_UP, "t2", "x", status=MoveStatus.INTERRUPTED
        ),
    )
    return s


def test_mapping_round_trip() -> None:
    s = played_session()
    assert from_dict(to_dict(s)) == s


def test_unknown_schema_version_is_rejected() -> None:
    data = to_dict(played_session())
    data["schema_version"] = 99
    with pytest.raises(ValueError, match="schema version"):
        from_dict(data)


async def test_save_load_list_delete(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    s = played_session()
    await store.save(s)
    s.end(EndReason.USER_ENDED, 20)
    await store.save(s)

    loaded = await store.load(SESSION_ID)
    assert loaded == s
    assert [x.status for x in await store.summaries()] == [SessionStatus.ENDED]
    assert not list((tmp_path / SESSION_ID).glob("*.tmp"))

    assert await store.delete(SESSION_ID)
    assert not (tmp_path / SESSION_ID).exists()
    assert await store.load(SESSION_ID) is None
    assert not await store.delete(SESSION_ID)


@pytest.mark.parametrize("bad_id", ["../etc", "A" * 32, "abc", "a" * 31 + "/"])
async def test_ids_cannot_escape_the_store(tmp_path: Path, bad_id: str) -> None:
    store = FileSessionStore(tmp_path / "sessions")
    assert await store.load(bad_id) is None
    assert not await store.delete(bad_id)
    with pytest.raises(ValueError, match="invalid session id"):
        store.session_dir(bad_id)


def test_voice_modality_round_trip() -> None:
    s = make_session(session_id=SESSION_ID, modality=Modality.VOICE)
    assert from_dict(to_dict(s)).config.modality is Modality.VOICE


def test_sessions_written_before_voice_support_load_as_text() -> None:
    data = to_dict(played_session())
    del data["config"]["modality"]
    assert from_dict(data).config.modality is Modality.TEXT


async def test_answer_audio_and_metrics_are_removed_with_the_session(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    await store.save(played_session())
    audio = PcmAudio(tone(0.5))
    await store.save_turn_audio(SESSION_ID, 1, Speaker.CANDIDATE, audio)
    await store.append_metrics(SESSION_ID, {"kind": "turn", "answer_turn_seq": 1})
    await store.append_metrics(SESSION_ID, {"kind": "turn", "answer_turn_seq": 3})

    directory = tmp_path / SESSION_ID
    assert from_wav((directory / "audio" / "turn-0001-candidate.wav").read_bytes()) == audio
    lines = (directory / "metrics.jsonl").read_text("utf-8").splitlines()
    assert [json.loads(line)["answer_turn_seq"] for line in lines] == [1, 3]
    assert not list(directory.rglob("*.tmp"))

    assert await store.delete(SESSION_ID)
    assert not directory.exists()


async def test_a_finished_interview_is_exported(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    session = played_session()
    session.resume(17)
    session.end(EndReason.USER_ENDED, 30)
    await store.save(session)
    question = PcmAudio(bytes(2 * 22_050), 22_050)  # one second at the voice's rate
    answer = PcmAudio(tone(2.0))
    await store.save_turn_audio(SESSION_ID, 0, Speaker.INTERVIEWER, question)
    await store.save_turn_audio(SESSION_ID, 1, Speaker.CANDIDATE, answer)
    await store.export(session)

    directory = tmp_path / SESSION_ID
    document = json.loads((directory / "transcript.json").read_text("utf-8"))
    assert document["session_id"] == SESSION_ID
    assert document["end_reason"] == "user_ended"
    assert document["audio"] == "audio/interview.wav"
    assert [(t["speaker"], t["text"], t["audio"]) for t in document["turns"]] == [
        ("interviewer", "Progetto?", "audio/turn-0000-interviewer.wav"),
        ("candidate", "Un servizio di routing.", "audio/turn-0001-candidate.wav"),
        ("interviewer", "x", None),  # the interrupted move: no audio
    ]
    assert document["turns"][2]["status"] == "interrupted"

    markdown = (directory / "transcript.md").read_text("utf-8")
    assert "**Interviewer** · 0:01" in markdown
    assert "> Un servizio di routing." in markdown
    assert "(interrupted)" in markdown

    whole = from_wav((directory / "audio" / "interview.wav").read_bytes())
    assert whole.sample_rate == 22_050  # the highest of the two rates
    assert whole.duration_s == pytest.approx(1.0 + 0.6 + 2.0, abs=0.01)


async def test_a_text_interview_exports_only_the_transcript(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    session = played_session()
    session.end(EndReason.USER_ENDED, 30)
    await store.export(session)
    document = json.loads((tmp_path / SESSION_ID / "transcript.json").read_text("utf-8"))
    assert document["audio"] is None
    assert all(t["audio"] is None for t in document["turns"])
    assert not (tmp_path / SESSION_ID / "audio").exists()
