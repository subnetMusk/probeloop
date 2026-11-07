"""The files of a session: one directory per session under the data volume.

Each directory holds:

- `audio/turn-NNNN-<speaker>.wav`, the audio of every turn of a voice interview (answers at
  16 kHz, the interviewer at its voice's rate);
- once the interview is over, `transcript.json`, `transcript.md` and `audio/interview.wav` (the
  whole conversation in one file). The transcript files are written again whenever an answer
  gets a new revision.

The structured state lives in the database; deleting a session removes this directory too.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from probeloop.interview.domain.model import InterviewSession, Speaker
from probeloop.speech.arrays import concatenate
from probeloop.speech.audio import PcmAudio, from_wav, to_wav
from probeloop.storage.exports import transcript_document, transcript_markdown

TURN_GAP_S = 0.6  # silence between turns in the combined audio
COMBINED_AUDIO = "audio/interview.wav"

_ID = re.compile(r"^[0-9a-f]{32}$")
# The files a client may download: the exports and the audio of a turn or of the whole interview.
_ARTIFACT = re.compile(
    r"^(transcript\.json|transcript\.md|audio/interview\.wav"
    r"|audio/turn-\d{4}-(interviewer|candidate)\.wav)$"
)


class SessionFiles:
    def __init__(self, root: Path) -> None:
        self._root = root
        root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def session_dir(self, session_id: str) -> Path:
        if not _ID.match(session_id):
            raise ValueError("invalid session id")
        return self._root / session_id

    def artifact(self, session_id: str, name: str) -> Path | None:
        """A downloadable file of the session, or None. `name` is checked against a fixed list,
        so it cannot reach outside the session directory."""
        if not _ARTIFACT.match(name):
            return None
        try:
            path = self.session_dir(session_id) / name
        except ValueError:
            return None
        return path if path.is_file() else None

    def write_turn_audio(
        self, session_id: str, turn_seq: int, speaker: Speaker, audio: PcmAudio
    ) -> None:
        directory = self.session_dir(session_id) / "audio"
        directory.mkdir(parents=True, exist_ok=True)
        atomic_write(directory / turn_audio_name(turn_seq, speaker), to_wav(audio))

    def read_turn_audio(self, session_id: str, turn_seq: int, speaker: Speaker) -> PcmAudio | None:
        path = self.session_dir(session_id) / "audio" / turn_audio_name(turn_seq, speaker)
        return from_wav(path.read_bytes()) if path.is_file() else None

    def export(self, session: InterviewSession, *, audio: bool = True) -> None:
        """Write the transcript files and, unless `audio` is False, the combined audio."""
        directory = self.session_dir(session.id)
        directory.mkdir(parents=True, exist_ok=True)
        turn_audio: dict[int, str] = {}
        recordings: list[PcmAudio] = []
        for turn in session.turns:
            path = directory / "audio" / turn_audio_name(turn.seq, turn.speaker)
            if path.is_file():
                turn_audio[turn.seq] = path.relative_to(directory).as_posix()
                if audio:
                    recordings.append(from_wav(path.read_bytes()))
        combined = None
        if audio and recordings:
            atomic_write(
                directory / COMBINED_AUDIO, to_wav(concatenate(recordings, gap_s=TURN_GAP_S))
            )
        if (directory / COMBINED_AUDIO).is_file():
            combined = COMBINED_AUDIO
        document = transcript_document(session, turn_audio, combined)
        text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        atomic_write(directory / "transcript.json", text.encode("utf-8"))
        atomic_write(directory / "transcript.md", transcript_markdown(document).encode("utf-8"))

    def remove(self, session_id: str) -> None:
        try:
            directory = self.session_dir(session_id)
        except ValueError:
            return
        shutil.rmtree(directory, ignore_errors=True)


def turn_audio_name(turn_seq: int, speaker: Speaker) -> str:
    return f"turn-{turn_seq:04d}-{speaker.value}.wav"


def atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
