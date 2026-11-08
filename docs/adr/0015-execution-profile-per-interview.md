# 0015 — Execution profile per interview

- Status: Accepted (amends 0013)
- Date: 2026-11-08

## Context

[ADR 0013](0013-cloud-execution-profile.md) made the execution profile global: local Ollama
models, or ChatGPT models through the user's ChatGPT plan. Every model call reads the current
selection, and the selection changes only when no interview is connected and no job runs.

The owner wants to choose the profile in the first step of each new interview. Two problems
follow from keeping it global:

- **Mixed models within one interview.** An interview paused with no client connected does not
  block a switch, so it can resume on the other profile.
- **Reports on the wrong profile.** A report generated after a switch uses the new profile, not
  the one the interview ran on.

## Decision

**Where the profile is stored.**
- Preparations and interview sessions store their execution profile (`local` or `cloud`).
- The setting in Settings becomes the default for new preparations. Changing it no longer needs
  an idle guard, because work already started keeps its own profile.

**How calls follow it.**
- **The interviewer** of a session is bound explicitly to the session's profile when the session
  is opened.
- **Calls made inside a request or a job** run inside a scope that selects the profile:
  - the topic planning when an interview is created;
  - the job offer draft;
  - the document analysis;
  - the CV check;
  - the interview review.

  The scope is a context variable that `ProfiledChatModel` reads before the default and always
  resets on exit.
- **Jobs** carry the profile in their payload:
  - an analysis uses its preparation's profile;
  - a CV check uses the profile requested by the preparation flow;
  - an interview report always uses the session's profile.

**Rules for the cloud profile.**
- Creating a preparation or an interview with the cloud profile requires a sign-in with plan
  usage.
- Resuming a cloud interview first checks the sign-in. It never falls back to the local models.

**Legacy rows.** Rows created before this change have no profile and use the current default,
which reproduces the old behaviour.

## Consequences

- An interview, its analysis and its reports always use one profile, and the report records the
  model that produced it.
- The paused-interview gap of ADR 0013 is closed.
- Jobs queued before the upgrade have no profile in their payload and use the default.
- Signing out still waits for idle work, because it can affect a running cloud job.

## Alternatives considered

- **Keeping the profile global and switching it from step 1** — simpler, but it keeps both
  problems above.
- **Passing the profile through every application call** — explicit, but it would thread an
  infrastructure choice through domain and application signatures that do not care about it.
