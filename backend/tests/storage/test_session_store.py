from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.context.domain.model import RoleProfile
from probeloop.interview.domain.model import (
    EndReason,
    InterviewerTurn,
    MovePurpose,
    RevisionSource,
    SessionStatus,
    Speaker,
    TranscriptWord,
    TurnIntent,
)
from probeloop.speech.audio import PcmAudio, from_wav
from probeloop.storage.database import current_revision, downgrade
from probeloop.storage.sql_sessions import SqlSessionStore
from tests.speech_audio import tone
from tests.storage.conftest import SESSION_ID, played_session


async def test_adaptive_intent_and_topic_clock_survive_reloading(store: SqlSessionStore) -> None:
    session = played_session()
    session.context = replace(
        session.context,
        policy_version="adaptive.v1",
        role_profile=RoleProfile("Economics", "Economist", "junior", confirmed=True),
        document_kinds=(("synthetic-cv", "cv"),),
    )
    turn = session.turns[0]
    assert isinstance(turn, InterviewerTurn)
    session.turns[0] = replace(
        turn,
        move=replace(
            turn.move,
            intent=TurnIntent(
                MovePurpose.NEW_TOPIC,
                elicited_criteria=("reasoning",),
                answer_limit="cannot_recall",
                focus="How the candidate would check an uncertain estimate.",
            ),
        ),
    )
    session.topic_engagement_s = {"t2": 51.25}
    session.execution_profile = (
        '{"version":1,"tools":{"interviewer":"local","analysis":"cloud",'
        '"evaluation":"cloud","limits":"laya"}}'
    )
    await store.save(session)
    try:
        assert await store.load(session.id) == session
    finally:
        # The PostgreSQL fixture downgrades between cases; mixed plans cannot be narrowed.
        await store.delete(session.id)


async def test_mixed_plans_cannot_be_downgraded_or_lost(
    store: SqlSessionStore, engine: AsyncEngine
) -> None:
    session = played_session()
    session.execution_profile = json.dumps(
        {
            "version": 1,
            "tools": {
                "interviewer": "local",
                "analysis": "cloud",
                "evaluation": "cloud",
                "limits": "laya",
            },
        }
    )
    await store.save(session)
    try:
        with pytest.raises(RuntimeError, match="cannot downgrade"):
            await downgrade(engine, "0006")
        assert await current_revision(engine) == "0007"
        assert await store.load(session.id) == session
    finally:
        await store.delete(session.id)


async def test_save_load_list_delete(store: SqlSessionStore) -> None:
    s = played_session()
    await store.save(s)
    s.end(EndReason.USER_ENDED, 20)
    await store.save(s)
    await store.save(s)  # saving again without changes is harmless

    assert await store.load(SESSION_ID) == s
    summaries = await store.summaries()
    assert [(x.id, x.status, x.ended_at) for x in summaries] == [
        (SESSION_ID, SessionStatus.ENDED, 20)
    ]
    summary = summaries[0]
    # Started at 10, paused from 16 and ended at 20: six seconds of interview.
    assert (summary.effective_s, summary.answers) == (6, 1)
    assert (summary.difficulty, summary.target_duration_s) == (
        s.config.difficulty.value,
        s.config.target_duration_s,
    )

    assert await store.delete(SESSION_ID)
    assert await store.load(SESSION_ID) is None
    assert not await store.delete(SESSION_ID)
    assert await store.summaries() == []


async def test_summaries_are_newest_first(store: SqlSessionStore) -> None:
    older, newer = played_session("b" * 32), played_session("c" * 32)
    newer.created_at = 5.0
    await store.save(older)
    await store.save(newer)
    assert [s.id for s in await store.summaries()] == ["c" * 32, "b" * 32]


async def test_summaries_measure_only_interviews_that_stopped(store: SqlSessionStore) -> None:
    paused = played_session("d" * 32)  # started at 10, paused at 16
    running = played_session("e" * 32)
    running.resume(18)
    fresh = played_session("f" * 32)
    fresh.started_at = None
    for s in (paused, running, fresh):
        await store.save(s)
    measured = {s.id: s.effective_s for s in await store.summaries()}
    assert measured == {"d" * 32: 6, "e" * 32: None, "f" * 32: None}


async def test_revisions_are_appended_and_kept(store: SqlSessionStore) -> None:
    s = played_session()
    s.end(EndReason.USER_ENDED, 20)
    await store.save(s)
    words = (TranscriptWord("Un", 0.0, 0.2, 0.98), TranscriptWord("servizio", 0.2, 0.7, 0.41))
    s.revise_answer(
        1,
        "Un servizio di routing HTTP.",
        RevisionSource.RETRANSCRIPTION,
        30,
        engine_ref="faster-whisper/large-v3-turbo",
        words=words,
    )
    await store.save(s)
    s.revise_answer(1, "Un servizio di routing HTTP/2.", RevisionSource.USER_EDIT, 40)
    await store.save(s)

    loaded = await store.load(SESSION_ID)
    assert loaded == s
    assert loaded is not None
    answer = loaded.candidate_turns()[0]
    assert [(r.number, r.source) for r in answer.revisions] == [
        (1, RevisionSource.STT),
        (2, RevisionSource.RETRANSCRIPTION),
        (3, RevisionSource.USER_EDIT),
    ]
    assert answer.revisions[1].words == words
    assert answer.text == "Un servizio di routing HTTP/2."


async def test_deleting_a_session_removes_rows_audio_and_metrics(
    store: SqlSessionStore, tmp_path: Path
) -> None:
    await store.save(played_session())
    audio = PcmAudio(tone(0.5))
    await store.save_turn_audio(SESSION_ID, 1, Speaker.CANDIDATE, audio)
    await store.append_metrics(SESSION_ID, {"kind": "turn", "answer_turn_seq": 1})
    await store.append_metrics(SESSION_ID, {"kind": "turn", "answer_turn_seq": 3})

    directory = tmp_path / "sessions" / SESSION_ID
    assert from_wav((directory / "audio" / "turn-0001-candidate.wav").read_bytes()) == audio
    assert await store.load_turn_audio(SESSION_ID, 1, Speaker.CANDIDATE) == audio
    assert await store.load_turn_audio(SESSION_ID, 1, Speaker.INTERVIEWER) is None
    assert [m["answer_turn_seq"] for m in await store.metrics(SESSION_ID)] == [1, 3]

    assert await store.delete(SESSION_ID)
    assert not directory.exists()
    assert await store.metrics(SESSION_ID) == []


async def test_a_finished_interview_is_exported(store: SqlSessionStore, tmp_path: Path) -> None:
    session = played_session()
    session.resume(17)
    session.end(EndReason.USER_ENDED, 30)
    await store.save(session)
    question = PcmAudio(bytes(2 * 22_050), 22_050)  # one second at the voice's rate
    answer = PcmAudio(tone(2.0))
    await store.save_turn_audio(SESSION_ID, 0, Speaker.INTERVIEWER, question)
    await store.save_turn_audio(SESSION_ID, 1, Speaker.CANDIDATE, answer)
    await store.export(session)

    directory = tmp_path / "sessions" / SESSION_ID
    document = json.loads((directory / "transcript.json").read_text("utf-8"))
    assert document["session_id"] == SESSION_ID
    assert document["end_reason"] == "user_ended"
    assert document["audio"] == "audio/interview.wav"
    assert [(t["speaker"], t["text"], t["audio"]) for t in document["turns"]] == [
        ("interviewer", "Progetto?", "audio/turn-0000-interviewer.wav"),
        ("candidate", "Un servizio di routing.", "audio/turn-0001-candidate.wav"),
        ("interviewer", "x", None),  # the interrupted move: no audio
    ]
    assert document["turns"][1]["revision_source"] == "stt"
    assert document["turns"][2]["status"] == "interrupted"

    markdown = (directory / "transcript.md").read_text("utf-8")
    assert "**Interviewer** · 0:01" in markdown
    assert "> Un servizio di routing." in markdown
    assert "(interrupted)" in markdown

    whole = from_wav((directory / "audio" / "interview.wav").read_bytes())
    assert whole.sample_rate == 22_050  # the highest of the two rates
    assert whole.duration_s == pytest.approx(1.0 + 0.6 + 2.0, abs=0.01)
    combined = directory / "audio" / "interview.wav"
    assert store.artifact(SESSION_ID, "audio/interview.wav") == combined

    # A revision rewrites the transcript files; the combined audio is kept as it is.
    session.revise_answer(1, "Un servizio di routing HTTP.", RevisionSource.USER_EDIT, 40)
    await store.export(session, audio=False)
    document = json.loads((directory / "transcript.json").read_text("utf-8"))
    assert document["turns"][1]["text"] == "Un servizio di routing HTTP."
    assert document["turns"][1]["revision"] == 2
    assert document["audio"] == "audio/interview.wav"


async def test_a_text_interview_exports_only_the_transcript(
    store: SqlSessionStore, tmp_path: Path
) -> None:
    session = played_session()
    session.end(EndReason.USER_ENDED, 30)
    await store.export(session)
    directory = tmp_path / "sessions" / SESSION_ID
    document = json.loads((directory / "transcript.json").read_text("utf-8"))
    assert document["audio"] is None
    assert all(t["audio"] is None for t in document["turns"])
    assert not (directory / "audio").exists()


@pytest.mark.parametrize(
    "name",
    [
        "../x",
        "session.json",
        "audio/../transcript.json",
        "audio/turn-1-candidate.wav",
        "/etc/passwd",
    ],
)
async def test_only_known_files_are_served(store: SqlSessionStore, name: str) -> None:
    session = played_session()
    session.end(EndReason.USER_ENDED, 30)
    await store.export(session)
    assert store.artifact(SESSION_ID, "transcript.json") is not None
    assert store.artifact(SESSION_ID, name) is None
    assert store.artifact("../" + SESSION_ID, "transcript.json") is None


@pytest.mark.parametrize("bad_id", ["../etc", "A" * 32, "abc", "a" * 31 + "/"])
async def test_ids_cannot_escape_the_files_root(store: SqlSessionStore, bad_id: str) -> None:
    assert await store.load(bad_id) is None
    assert not await store.delete(bad_id)
    with pytest.raises(ValueError, match="invalid session id"):
        store.files.session_dir(bad_id)
