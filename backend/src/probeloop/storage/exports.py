"""What a finished interview leaves for the candidate: the transcript as JSON and Markdown.

The JSON is the full record (one entry per turn, with the audio file of the turn when there is
one); the Markdown is the same conversation for reading.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from probeloop.interview.domain.model import CandidateTurn, InterviewSession

EXPORT_VERSION = 1


def _iso(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, UTC).isoformat(timespec="seconds")


def clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def transcript_document(
    session: InterviewSession, turn_audio: Mapping[int, str], combined_audio: str | None
) -> dict[str, Any]:
    """The full record. Audio paths are relative to the session directory."""
    config = session.config
    turns: list[dict[str, Any]] = []
    for turn in session.turns:
        entry: dict[str, Any] = {
            "seq": turn.seq,
            "speaker": turn.speaker.value,
            "elapsed_s": round(turn.elapsed_s, 1),
        }
        if isinstance(turn, CandidateTurn):
            entry["text"] = turn.text
        else:
            move = turn.move
            entry |= {
                "text": move.utterance,
                "action": move.action.value,
                "topic_id": move.topic_id,
                "status": move.status.value,
                "fallback": move.fallback,
            }
        entry["audio"] = turn_audio.get(turn.seq)
        turns.append(entry)
    ended_at = session.ended_at
    return {
        "export_version": EXPORT_VERSION,
        "session_id": session.id,
        "interview_type": config.interview_type.value,
        "difficulty": config.difficulty.value,
        "language": config.language.value,
        "modality": config.modality.value,
        "target_duration_s": config.target_duration_s,
        "started_at": _iso(session.started_at),
        "ended_at": _iso(ended_at),
        "duration_s": round(session.elapsed_s(ended_at), 1) if ended_at else None,
        "status": session.status.value,
        "end_reason": session.end_reason.value if session.end_reason else None,
        "failure": session.failure,
        "topics": [
            {"id": t.id, "title": t.title, "coverage": session.coverage[t.id].value}
            for t in session.context.topics
        ],
        "audio": combined_audio,
        "turns": turns,
    }


def transcript_markdown(document: Mapping[str, Any]) -> str:
    lines = [
        "# Interview transcript",
        "",
        "| | |",
        "|---|---|",
        f"| Session | `{document['session_id']}` |",
        f"| Interview | {document['interview_type']}, {document['difficulty']}, "
        f"{document['language']}, {document['modality']} |",
        f"| Started | {document['started_at'] or '-'} |",
    ]
    if document["duration_s"] is not None:
        lines.append(
            f"| Duration | {clock(document['duration_s'])} of "
            f"{clock(document['target_duration_s'])} |"
        )
    end = document["end_reason"] or document["failure"] or document["status"]
    lines.append(f"| End | {end} |")
    if document["audio"]:
        lines.append(f"| Audio | [{document['audio']}]({document['audio']}) |")
    lines += ["", "## Conversation", ""]
    for turn in document["turns"]:
        speaker = "Interviewer" if turn["speaker"] == "interviewer" else "Candidate"
        note = " (interrupted)" if turn.get("status") == "interrupted" else ""
        lines.append(f"**{speaker}** · {clock(turn['elapsed_s'])}{note}")
        lines.append("")
        text = turn["text"].strip() or "_(no speech recognised)_"
        lines += [f"> {line}" for line in text.splitlines()]
        lines.append("")
    return "\n".join(lines)
