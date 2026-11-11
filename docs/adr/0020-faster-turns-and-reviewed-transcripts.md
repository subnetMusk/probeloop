# 0020 — Faster interviewer turns, optional Jev and reviewed transcripts

- Status: Accepted
- Date: 2026-11-11
- Amends: 0016, 0017, 0018, 0019

## Context

Measured on recorded voice interviews, the recruiter's next question started 17–19 s after the
candidate stopped speaking. Most of that time was two sequential model calls per adaptive turn:
a validated decision, then the question. The live recogniser also made many recognition errors,
so the conversation was hard to read afterwards, and a cold recogniser once lost the start of the
first answer: its first audio took about a minute, beyond the 15 s budget of a segment.

Laya, the local stated-limit classifier, needs a machine that can run it. TypeSafe Jev, a hosted
classifier, was evaluated on the same items. Its wording-tuned prompt at threshold 0.5 met the
acceptance criteria for stated limits; it did not for the interview decision itself.

The evaluation is recorded in the research document of 11 November 2026 (experiments E1 and
trials 1–4); its data stays under `var/test-run/`.

## Decision

**Turn mode.** `PROBELOOP_INTERVIEWER_TURN` defaults to `auto`: the cloud interviewer writes the
move in one constrained call (decision fields before the utterance, illegal choices excluded by the
schema, one corrective retry before anything is spoken); a local interviewer keeps two steps.
`single` and `two_step` remain available.

**Jev.** Stated-limit reading accepts a fourth tool, Jev, besides the local LLM, ChatGPT and Laya.
It is optional and needs a pay-as-you-go API key, verified before it is stored (owner-only file,
never returned by the API). Laya remains optional too.

**Preparation.** Before the first question the interview loads, and uses once, every engine it
will need: the language model, the stated-limit reader of adaptive interviews, the recogniser
(two seconds of silence) and the voice. A first use that outlasts a request's timeout is repeated
until the start's deadline, since the services keep loading meanwhile. The interview starts only
when every step is ready; the client shows each step.

**Lost segments.** A segment whose recognition fails is set aside and retried as soon as the
recogniser answers another segment, and once more before the final transcript. Only then is the
answer recorded as incomplete.

**Answer reconstruction.** In voice interviews the cloud interviewer may also return, after the
question, its reading of the answer it replies to. It is stored as a new revision; the live
transcript and the audio are kept. The reading is discarded when it changes the length too much or
keeps fewer than 60% of the live text's content words, and skipped when the context window cannot
hold it. It is a Settings preference, off by default and applied only with the ChatGPT interviewer:
local models measured so far rewrote answers and invented figures.

**Review before the report.** An answer is flagged when part of its audio was not recognised or
when an expected reading was not kept. Flags show beside the answer and in a review card until a
later revision (second transcription or manual edit) replaces the live text. Generating a report
from a spoken interview whose answers are flagged, or still in their live text, asks for
confirmation first.

**Whisper** stays an optional second transcription, recommended with the local interviewer.

**Background work.** New interviews still wait for running jobs; the final check shows which job
is running and how far it is.

## Consequences

- With ChatGPT the median time to the next question fell to about 5 s in voice trials.
- The first answer no longer depends on a warm recogniser; a slow preparation is visible instead.
- Jev sends each answer's sentences and the question to TypeSafe when selected.
- A database migration adds the answer's review flags to the stored turns.
- Answer reconstruction was measured on synthetic speech; real speech may differ, so it remains
  optional and every earlier revision stays available.
