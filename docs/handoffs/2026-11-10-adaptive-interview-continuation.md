# Adaptive interview continuation

Date: 2026-11-10. This note records implementation progress and development measurements, not
release acceptance. It continues
[the 2026-11-09 checkpoint](2026-11-09-adaptive-interview-continuation.md), whose remaining
acceptance list still applies.

## What changed

Synthetic candidates now have private histories, answer styles, sourced mistaken beliefs and
uploaded job offers or resources (`personas.v2.json`). Overall scores cover explored criteria
only, and autonomy is assessed wherever the interviewer gave a hint.

The adaptive interviewer prompt is fitted to the model context window. An adaptive turn can be
generated in one structured call or in two steps; see
[the adaptive policy](../architecture.md#adaptive-policy-and-public-score-scale). The two-step
turn was developed against five development conversations at a time:

1. Decisions are constrained to the objectives the policy admits, and to the closing purpose
   only while closing is admitted. Code makes the closing decision when it is the only legal
   move.
2. A started closing always ends, and fallback moves no longer ask for a recorded answer again.
3. A narrow call reads the limits stated in the latest answer before the decision. Their quotes
   reach both steps.
4. The shared prompt reserves room for both steps and the quoted limits.

Recorded intents keep the decision focus and mark a stated limit. Development runs retry
transient failures of the simulated candidate and record client receive times.

Two-step is now the default turn for both execution profiles (`PROBELOOP_INTERVIEWER_TURN`,
passed through by compose). Code drops autonomy from questions that pose no reasoning task,
the cause of the three cloud two-step fallbacks, and the scripted model of the browser tests
answers every two-step call.

## Measurements

The comparison of single-call and two-step turns, with the audit of questions asked again after
a stated limit, is in the
[validation note](../research/adaptive-interview-validation.md#single-call-and-two-step-turns).
Raw sessions, summaries and label checks are under the ignored `var/test-run/turn-compare-v1/`.

Checks on the final tree: 588 backend tests passed (37 skipped, 22 live deselected), with ruff,
mypy and the nine import contracts. With the runtime image built before the closing-purpose
change and the scripted backend of `compose.test.yaml`, 15 browser tests passed and the two
live ones were skipped; CI ran the same suite on the last pushed commit. The real backend runs the
image rebuilt after that change, with two-step turns on `probeloop_data`.

## Development data in `probeloop_data`

The runs created synthetic development sessions in the real volume. Four were left by
interrupted runs and are kept, since nothing is deleted from that volume:

- `01a1c3b785a87218bfcf25e0cd7bbf4c`: economics junior, status `ready`, no turns. An early
  two-step run stopped before the first question.
- `01a1c3ce5aa67ff2950a303e04c515ec`: economics senior, ended by the user action after 27
  turns. A provider error of the simulated candidate stopped the run before candidate retries
  existed.
- `01a1c5637c3674bda4c063e16082fe9b`: healthcare junior with the cloud interviewer and
  single-call turns, still `in_progress` after 11 turns. Docker Desktop stopped answering and
  restarted the containers during the run; the case was run again.
- `01a1c588cd867d28ac0e68fbe59d6f81`: software senior with the cloud interviewer and two-step
  turns after the autonomy repair, `paused` after 25 turns. The provider failed the simulated
  candidate's request three times in a row.

## Operating notes

- The backend `/tmp` is a tmpfs and is emptied whenever the container restarts, including when
  Docker Desktop restarts it. Copy the eval driver with a tar stream from `backend/`, for
  example `tar --exclude='__pycache__' -cf - evals | docker exec -i probeloop-backend-1 tar -C /tmp -xf -`,
  and save run outputs before any recreate.
- On this host BuildKit could not fetch the external Dockerfile frontend named by the
  `# syntax=docker/dockerfile:1` line. Building with the built-in frontend works from the
  repository root:
  `sed 1d docker/backend.Dockerfile | docker build --target runtime -t probeloop-backend:runtime -f - .`
  The Dockerfile is unchanged.
- One recreate failed because a process left by `docker exec` was a zombie that Docker could
  not kill. The old container stopped on its own shortly after (exit 137), the volume was
  intact, and the retried recreate succeeded. Running the backend with an init process would
  reap such processes; it is not configured.

## Open items

1. Independent cases (teaching and industrial quality, two levels each) have not run. Freeze
   the implementation first and never adjust a prompt on their transcripts.
2. The gate audits are still to do on full conversations: relevance of every probe (at least
   90%), invented personal references, lost answers and penalties on unelicited abilities.
3. The local five-repeat calibration of `adaptive-pair-v1` and the four voice tests are still
   to run.
4. With the cloud interviewer the first words of a two-step turn came after a median of 11 to
   21 s of model time, against about 5 s for a single call, which falls back far more often.
   The voice tests should show whether that profile needs single-call turns or a faster step.
5. In the last cloud check one of 30 moves fell back after two decisions gave a closing purpose
   to an ordinary objective while closing was not yet allowed. The schema now leaves that
   purpose out, and one cloud conversation with it had no fallback; a single conversation
   does not show that the cause is gone.
6. Limits are read from the latest answer only, so a detail forgotten earlier in an episode can
   be asked for again later. About one in six answers with a stated limit is still followed by
   a question asking for it again.
7. A question moved to a hypothetical after a stated limit can keep the decision's past flag
   (3 of 62 turns in the last local run), which would enable experience criteria for it.
8. Laya weights are kept in the ignored `var/models/laya-multilingual`. Recorded intents of both
   profiles are structured labels; before any fine-tuning, labels written by the local model
   are relabelled once by the cloud classifier.
