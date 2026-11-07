from __future__ import annotations

import json
from pathlib import Path

import pytest

from probeloop.interview.domain.model import Modality, RevisionSource
from probeloop.storage.legacy_import import from_dict, import_file_sessions, to_dict
from probeloop.storage.sql_sessions import SqlSessionStore
from tests.conftest import make_session
from tests.storage.conftest import SESSION_ID, played_session


def test_mapping_round_trip() -> None:
    s = played_session()
    # The old format had no revision metadata: the answer comes back as the live transcript.
    loaded = from_dict(to_dict(s))
    assert loaded.turns[0] == s.turns[0]
    answer = loaded.candidate_turns()[0]
    assert answer.text == "Un servizio di routing."
    assert [(r.number, r.source) for r in answer.revisions] == [(1, RevisionSource.STT)]


def test_unknown_schema_version_is_rejected() -> None:
    data = to_dict(played_session())
    data["schema_version"] = 99
    with pytest.raises(ValueError, match="schema version"):
        from_dict(data)


def test_sessions_written_before_voice_support_load_as_text() -> None:
    data = to_dict(played_session())
    del data["config"]["modality"]
    assert from_dict(data).config.modality is Modality.TEXT
    voice = to_dict(make_session(session_id=SESSION_ID, modality=Modality.VOICE))
    assert from_dict(voice).config.modality is Modality.VOICE


async def test_old_sessions_are_imported_once(store: SqlSessionStore, tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    old = root / SESSION_ID
    (old / "audio").mkdir(parents=True)
    (old / "session.json").write_text(json.dumps(to_dict(played_session())), "utf-8")
    (old / "metrics.jsonl").write_text('{"answer_turn_seq": 1}\n{"answer_turn_seq": 3}\n', "utf-8")
    broken = root / ("b" * 32)
    broken.mkdir()
    (broken / "session.json").write_text("{}", "utf-8")

    result = await import_file_sessions(root, store)
    assert result.imported == [SESSION_ID]
    assert result.failed == ["b" * 32]
    loaded = await store.load(SESSION_ID)
    assert loaded is not None
    assert loaded.candidate_turns()[0].text == "Un servizio di routing."
    assert [m["answer_turn_seq"] for m in await store.metrics(SESSION_ID)] == [1, 3]
    assert (old / "session.imported.json").is_file()
    assert not (old / "metrics.jsonl").exists()

    again = await import_file_sessions(root, store)
    assert again.imported == []
