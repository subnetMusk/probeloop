"""The transcript of a finished interview: corrections by the user and the refinement pass.

Every change makes a new revision of an answer; earlier revisions are kept. After a revision the
transcript files are written again, so the exports always show the current text.

The refinement job re-transcribes every stored answer with the accurate recogniser (Whisper,
with a vocabulary prompt when there is one). It runs after the call, never during it: during the
call the extra memory would slow down the live path (see the evaluation proposal, section 4.5).
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

from probeloop.interview.application.ports import Clock, SessionStore
from probeloop.interview.domain.model import (
    CandidateTurn,
    InterviewSession,
    RevisionSource,
    Speaker,
    TranscriptWord,
)
from probeloop.platform.jobs import Job, JobError, Progress
from probeloop.speech.filters import rejection_reason
from probeloop.speech.ports import SpeechError, SpeechToText, TranscribeOptions

logger = logging.getLogger(__name__)

REFINE_JOB = "refine_transcript"
MIN_AUDIO_S = 0.3
MAX_EDIT_CHARS = 10_000


class TranscriptNotFoundError(LookupError):
    pass


class TranscriptService:
    def __init__(
        self,
        *,
        store: SessionStore,
        clock: Clock,
        refiner: SpeechToText | None = None,
        vocabulary: Callable[[InterviewSession], str | None] = lambda _: None,
        refinement_enabled: Callable[[], bool] = lambda: True,
    ) -> None:
        self._store = store
        self._clock = clock
        self._refiner = refiner
        self._vocabulary = vocabulary
        self._refinement_enabled = refinement_enabled
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @property
    def can_refine(self) -> bool:
        return self._refiner is not None and self._refinement_enabled()

    async def edit(self, session_id: str, turn_seq: int, text: str) -> CandidateTurn:
        """A correction typed by the user becomes a new revision of the answer."""
        if len(text) > MAX_EDIT_CHARS:
            raise ValueError(f"an answer is limited to {MAX_EDIT_CHARS} characters")
        async with self._locks[session_id]:
            session = await self._load(session_id)
            turn = session.revise_answer(
                turn_seq, text, RevisionSource.USER_EDIT, self._clock.now()
            )
            await self._store.save(session)
        await self._store.export(session, audio=False)
        return turn

    async def refine(self, job: Job, progress: Progress) -> Mapping[str, Any]:
        """Job handler: re-transcribe every stored answer of the session."""
        if self._refiner is None or not self._refinement_enabled():
            raise JobError("speech recognition is not configured")
        session = await self._load(job.subject_id)
        answers = session.candidate_turns()
        prompt = self._vocabulary(session)
        options = TranscribeOptions(
            language=session.config.language.value, initial_prompt=prompt, word_timestamps=True
        )
        revised = skipped = 0
        for index, turn in enumerate(answers, start=1):
            audio = await self._store.load_turn_audio(session.id, turn.seq, Speaker.CANDIDATE)
            if audio is None or audio.duration_s < MIN_AUDIO_S:
                skipped += 1
            else:
                try:
                    result = await self._refiner.transcribe(audio, options)
                except SpeechError as exc:
                    raise JobError(f"speech recognition failed: {exc}") from exc
                segments = [
                    s
                    for s in result.segments
                    if rejection_reason(s.text, s.end_s - s.start_s) is None
                ]
                text = " ".join(s.text for s in segments)
                words = tuple(
                    TranscriptWord(w.text, w.start_s, w.end_s, w.probability)
                    for s in segments
                    for w in s.words
                )
                if text.strip():
                    async with self._locks[session.id]:
                        current = await self._load(session.id)
                        current.revise_answer(
                            turn.seq,
                            text,
                            RevisionSource.RETRANSCRIPTION,
                            self._clock.now(),
                            engine_ref=result.engine_ref,
                            words=words,
                        )
                        await self._store.save(current)
                    revised += 1
                else:
                    skipped += 1
            await progress(index / len(answers), f"{index}/{len(answers)}")
        await self._store.export(await self._load(session.id), audio=False)
        logger.info(
            "transcript refined",
            extra={"session_id": session.id, "revised": revised, "skipped": skipped},
        )
        return {"revised": revised, "skipped": skipped, "vocabulary": bool(prompt)}

    async def _load(self, session_id: str) -> InterviewSession:
        session = await self._store.load(session_id)
        if session is None:
            raise TranscriptNotFoundError(session_id)
        return session
