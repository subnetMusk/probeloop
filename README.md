# ProbeLoop

ProbeLoop is an open-source, self-hosted platform for practising job interviews with an AI
interviewer. The interview is a spoken conversation. The interviewer asks follow-up questions
based on your answers, your CV and the job offer. After the call you get a detailed report, and
you can track your progress across sessions.

> **Status: early development.** Document preparation, spoken interviews, transcript review and
> CV reviews are implemented. Interview reports, settings and data/history workflows are a
> development checkpoint with outstanding integration and model-quality acceptance. The first
> draft evaluator took 27 minutes for four question/answer pairs and produced a technical false
> positive. See the [continuation notes](docs/handoffs/2026-11-08-assessment-continuation.md) and
> [roadmap](docs/roadmap.md); these features are not yet declared complete.

## Goals

- **A realistic conversation.** The interviewer adapts to each answer: it digs deeper, asks for
  clarification, changes topic or wraps up, and it keeps track of what has already been
  discussed.
- **Faithful transcription.** Transcripts are reviewable and correctable before evaluation.
  Correcting a transcript lets you regenerate the report without repeating the interview.
- **Honest, verifiable feedback.** The evaluator is separate from the interviewer and applies
  versioned, interview-type-specific rubrics. Every judgement cites the transcript. Scores are
  formative measures, not predictions of hiring outcomes.
- **Traceable context.** Information extracted from your CV, the job offer and supplied resources
  keeps its provenance (declared, observed or inferred). You review and approve it before the
  interview starts.
- **Local first.** Inference runs on local models through [Ollama](https://ollama.com). No
  pay-per-use API is required and no cloud service is mandatory. Your documents, recordings and
  transcripts stay on your machine.

## Planned architecture

- A modular monolith built with hexagonal architecture (ports and adapters).
  - Backend: Python, FastAPI, Pydantic and SQLAlchemy. SQLite by default, PostgreSQL supported.
  - Frontend: React, TypeScript, Vite, Tailwind CSS and shadcn/ui.
- Speech recognition runs in a dedicated worker (faster-whisper or Parakeet). Speech synthesis
  runs as a separate Piper service.
- The interview uses explicit turn-taking. The interviewer speaks, you answer, and you press a
  button when you are done.
- Everything runs under Docker Compose.

See [docs/architecture.md](docs/architecture.md) for the full design.

## Running a voice interview

**Requirements**
- Docker with Compose.
- [Ollama](https://ollama.com) on the host, with the interviewer model:

  ```bash
  ollama pull ministral-3:8b
  ```

**Download the speech models** once (about 3 GB, into the `probeloop_models` volume). The speech
services run on an internal network without internet access, so they cannot fetch models
themselves:

```bash
docker compose --profile setup run --rm stt-models
```

```bash
docker compose --profile setup run --rm tts-voices
```

**Start everything.** Only the backend is published, on `127.0.0.1:8000`, and it serves the web
app:

```bash
docker compose up -d --build
```

Then open <http://127.0.0.1:8000>. The dashboard shows your recent practice, short paginated
lists, and score trends. Select **New interview** to prepare a call. Joining loads the language
model and the speech engines first, which can take a minute the first time. Use headphones if you
can: the microphone only records between "Answer" and "End of answer" (or the space bar), but
headphones keep the interviewer's voice out of the room.

**Prepare an interview in five steps.** Each step has its own URL. Back and Forward preserve
the draft in the current tab, including across a reload. Required fields carry `*`, and a disabled
Continue button explains what is missing.

1. **Interview settings:** language, type, difficulty, duration and processing profile. Choose
   local Ollama models or the ChatGPT plan signed in through Settings. Speech always stays local.
2. **Resource profile:** reuse a saved CV, job offer and resources, or prepare this interview only.
3. **Documents:** upload or paste a CV and an optional offer, or describe a role and edit its
   drafted offer. Add titled resources (text, Markdown, JSON, XML, HTML, DOCX or PDF). Changed
   profiles can be overwritten, copied or used once. Editing an upload keeps the original file.
4. **Fact review:** confirm, correct or exclude doubtful interpretations; the full list is
   collapsed. Without an offer, confirm the professional area. Approval freezes the context.
5. **Final check:** optionally check the CV against the offer, test the microphone and start.
   The CV check uses the interview language and processing profile.

By default, local document analysis and assessment use `qwen3.5:9b` (download it with
`ollama pull qwen3.5:9b`). No document link is followed. A quick start without documents remains
available. The chosen processing profile stays with the preparation and interview, including
reports generated later; changing the default in Settings does not change existing interviews.

**After the call** your answers are transcribed again from their recordings with Whisper, a
slower but more accurate recogniser (a few minutes for a 10-minute interview; the first run also
loads the model). **Interviews** lists past sessions: each has the recording, the transcript
with the doubtful words highlighted, and the downloads. Correcting an answer keeps the earlier
versions. The transcript groups questions and answers, with audio and revision history beside
each answer. **CV checks** and **Profiles** have their own detail pages and original-file links.

**Reports.** After reviewing the transcript, "Generate report" assesses the answers in the
background using the interview's processing profile; you can leave the page and a notice
appears when it is done. Each
answer is judged twice against an anchored rubric, every score needs a quotation that code finds
in the transcript, and technical corrections are model judgements, labelled as such. Regenerating
after a correction keeps the earlier versions. Reports export to Markdown, JSON and PDF, and the
CV can be reviewed the same way before the interview. Interview reports lead with the overall
score and summary, improvements and strengths, then each question and its assessed answers,
job requirements and delivery medians. Technical provenance is collapsed at the end. CV reports
show criterion reasons, the requirement matrix, checks in priority order, rewrites and practice
questions. Markdown and PDF use the same reading order, pinned by a shared synthetic fixture;
JSON preserves the raw report. How the evaluation works, and what it costs,
is in [docs/research/evaluation-latency.md](docs/research/evaluation-latency.md).

Screenshots below use synthetic data only.

![Dashboard with score trends](docs/fixtures/synthetic/ui/dashboard.png)
![Interview report with verified quotations](docs/fixtures/synthetic/ui/interview-report.png)
![Transcript with recording and revision history](docs/fixtures/synthetic/ui/transcript.png)
![Original synthetic CV in the inline PDF viewer](docs/fixtures/synthetic/ui/cv-preview.png)

**Your data.** Settings → Your data exports the structured data as JSON, or downloads a portable ZIP
backup with the documents, recordings, transcripts and reports (models and server configuration
are not included; the backup can contain personal data). Close open interviews and wait for
background jobs first. To restore, start from an empty instance, stop the backend and run the
restore command with the archive mounted into a one-off container:

```bash
docker compose run --rm --no-deps -v "$PWD/probeloop-backup.zip:/backup.zip:ro" backend probeloop restore-backup /backup.zip
```

The restore refuses a database or data directory that is not empty, archives with unsafe paths,
and backups from a newer version. Backups from an earlier version are upgraded while restoring. "Delete all my data" removes every interview, document, profile, report, export and log,
and resets the browser preferences.

**Your ChatGPT plan (optional).** By default every model runs locally. With a ChatGPT Plus or
Pro subscription, Settings → Execution profile → "Continue with ChatGPT" signs in through OpenAI.
The "ChatGPT plan" profile then runs the interviewer, document analysis and evaluation on ChatGPT
models (`gpt-6.1-terra` by default; see `PROBELOOP_CLOUD_*_MODEL` in `compose.yaml`). Usage counts
against your plan's limits, not pay-per-use API billing.

- Open the app on `127.0.0.1` or `localhost` at port 8000: the sign-in returns to
  `http://127.0.0.1:8000/auth/callback`.
- Speech recognition and synthesis always stay local. With this profile your CV, documents,
  transcripts and answers are sent to OpenAI; audio is not.
- The tokens are kept in the data volume (`chatgpt/credentials.json`, owner-only), never in the
  browser. They are excluded from backups. "Sign out of ChatGPT" revokes them.
- OpenAI currently offers this sign-in as a preview. Whether it accepts ProbeLoop's registration
  is only known after the first sign-in.

The design is in [ADR 0013](docs/adr/0013-cloud-execution-profile.md).

**What a session leaves** in the `probeloop_data` volume: the database `probeloop.db` (SQLite),
and under `sessions/<id>/` the files: `transcript.md` and `transcript.json` (the whole
conversation, rewritten after every correction), `audio/interview.wav` (both voices in one file)
and the audio of every turn. Deleting an interview removes its rows and its directory.

Sessions recorded before the database (M3) are moved into it once with:

```bash
docker compose exec backend probeloop import-sessions
```

**PostgreSQL** can replace SQLite (the `postgres` profile; sessions are not copied between the two):

```bash
PROBELOOP_POSTGRES_PASSWORD=change-me PROBELOOP_DATABASE_URL=postgresql+asyncpg://probeloop:change-me@postgres:5432/probeloop docker compose --profile postgres up -d
```

**A text interview** (no audio) still runs from inside the backend container. Type the answers;
`/pause`, `/resume` and `/end` control the session:

```bash
docker compose exec backend probeloop chat --type technical --language it --minutes 15
```

## Development

Hot reload for the backend, and Vite with hot module replacement on <http://127.0.0.1:5173>:

```bash
docker compose -f compose.yaml -f compose.dev.yaml watch
```

**Backend checks** run in the dev image:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend pytest
```

**Frontend checks** (ESLint, Prettier, TypeScript, Vitest, build) run in a Node container:

```bash
docker run --rm -v "$PWD:/repo" -w /repo/frontend node:24.22.0-trixie-slim sh -c "npm ci && npm run lint && npm run lint:fsd && npm run format:check && npm run typecheck && npm test && npm run build"
```

**API types.** The frontend's TypeScript types are generated from the backend's contract (OpenAPI
and the JSON Schema of the WebSocket messages); CI fails when they are out of date:

```bash
docker run --rm -v "$PWD/frontend/src/shared/api/contract:/out" probeloop-backend:dev python -m probeloop.api.contract /out
```

```bash
docker run --rm -v "$PWD/frontend:/work" -w /work node:24.22.0-trixie-slim npm run gen:types
```

**End-to-end test.** Playwright drives Chromium with a fake microphone against a backend that uses
a scripted interviewer and fake speech engines (no GPU or models needed):

```bash
docker compose -f compose.yaml -f compose.test.yaml up -d --build --no-deps backend
```

```bash
docker run --rm --network container:probeloop-backend-1 -v "$PWD:/repo" -w /repo/frontend mcr.microsoft.com/playwright:v1.65.0-noble sh -c "npm ci && npx playwright test"
```

Run `docker compose up -d --build backend` afterwards to restore the real engines. Verify that
`/data` mounts `probeloop_data`, not `probeloop_e2e_data`:

```bash
docker inspect probeloop-backend-1 --format '{{range .Mounts}}{{.Name}} {{.Destination}}{{end}}'
```

Frontend checks mount the repository root because Vitest also reads the backend's synthetic
report-outline fixture. Component tests use Testing Library and jsdom. Browser tests scan the
dashboard and preparation with axe, and check report and transcript pages in both themes. They
also check desktop alignment and mobile overflow. This is a WCAG 2.2 AA self-assessment,
not external certification;
the footer links to the current limitations.

For an explicit acceptance run with real models, start the real stack, ensure Ollama and speech
models are ready, and sign in with ChatGPT with plan usage enabled. The following opt-in browser
checks add a short synthetic interview and a CV check for each profile, uploading a PDF and DOCX.
They never delete data or change account settings:

```bash
docker run --rm --network container:probeloop-backend-1 -e PROBELOOP_LIVE_ACCEPTANCE=1 -v "$PWD:/repo" -w /repo/frontend mcr.microsoft.com/playwright:v1.65.0-noble npx playwright test e2e/live-acceptance.spec.ts
```

**Tests against real models** (`live` marker): the interviewer with Ollama, and the speech engines
in-process and through the running services:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm -e PROBELOOP_TEST_STT_URL=http://stt-worker:8000 -e PROBELOOP_TEST_TTS_URL=http://tts-piper:5000 backend pytest -m live
```

**Evaluations.** The interviewer with scripted text personas:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python -m evals.interviewer_personas
```

The interview evaluator on a labelled synthetic transcript, with a per-call trace (phase,
attempts, tokens, stop reason, duration) and labelled checks; `--judge-reasoning default` turns
thinking on for the judging passes and `--debug-log` keeps the raw synthetic prompts and outputs:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm -v "$PWD/var/test-run:/out" backend python -m evals.interview_review --output /out/interview-review.json --repetitions 3
```

The evaluator calibration with LLM personas (proposal section 6) uses generated weak/strong
answers to five topic cards. Generate and source-check the answers first: a model's requested
persona is not proof that it followed the label. The full run requires an audit matching their
hash, then reviews each answer five times. Use fresh output filenames; retain earlier measurements.

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm -v "$PWD/backend:/app" -v "$PWD/var/test-run:/out" backend python -m evals.persona_calibration --answers-only --persona-profile cloud --output /out/calibration-answers.json
docker compose -f compose.yaml -f compose.dev.yaml run --rm -v "$PWD/backend:/app" -v "$PWD/var/test-run:/out" backend python -m evals.persona_calibration --answers-from /out/calibration-answers.json --audit /out/calibration-audit.json --profile local --output /out/calibration-local.json
docker compose -f compose.yaml -f compose.dev.yaml run --rm -v "$PWD/backend:/app" -v "$PWD/var/test-run:/out" backend python -m evals.persona_calibration --answers-from /out/calibration-answers.json --audit /out/calibration-audit.json --profile cloud --output /out/calibration-cloud.json
```

Both scorers receive identical answers and keep the application/account defaults unchanged.
The cloud commands require an existing sign-in and enabled plan usage. `--cards indexes
--regenerations 1` makes a short probe; its result is not a complete calibration. See the
[audit format, thresholds and limitations](docs/research/persona-calibration-method.md).

A synthetic voice candidate takes a real voice interview against the running stack. Every question
is written to `var/voice-candidate/run-*/turn-NNNN-question.json`; whoever plays the candidate (a
person or an agent) writes the answer to `turn-NNNN-answer.txt` (`/end` ends the call), and the
tool speaks it with Piper. The run ends with a report of what was said, what was recognised (WER)
and the reply latency of every turn:

```bash
docker compose --profile tools run --rm voice-candidate --minutes 10
```

The synthetic candidate uses the male `it_IT-riccardo-x_low` voice; download it with
`docker compose --profile setup run --rm tts-voices it_IT-riccardo-x_low` first. Pass
`--snapshot-id <approved-id>` for a document-based interview, and `--voice` to choose another
downloaded candidate voice. [Voice credits and licences](docs/voices.md).

**Configuration** uses `PROBELOOP_*` environment variables
(see [settings.py](backend/src/probeloop/settings.py)). For example,
`PROBELOOP_INTERVIEWER_MODEL=qwen3.5:9b` switches the model, and `PROBELOOP_TTS_VOICE` the
interviewer's voice (`it_IT-serena-medium` by default; download others with the `tts-voices`
service). `PROBELOOP_LLM_DEBUG_LOG=true` writes prompts and outputs to `/data/logs/llm.jsonl`.
That log contains personal data, so it is off by default.

## Documentation

- [Architecture](docs/architecture.md)
- [Initial research](docs/research/2026-11-initial-research.md): reuse of existing projects, local
  LLMs, speech engines and realtime transport. It distinguishes documented facts, inferences and
  points that still need to be verified.
- [Roadmap](docs/roadmap.md)
- [Proposal: CV review, context, evaluation and reports](docs/proposals/2026-11-context-evaluation-reports.md)
- [Architecture decision records](docs/adr/)
- [Contributor and coding-agent conventions](AGENTS.md)

## Privacy

ProbeLoop processes personal data: CVs, job offers, voice recordings and transcripts.

- All of it is stored locally in Docker volumes. Only the optional ChatGPT plan profile sends
  text (not audio) to OpenAI, after a sign-in and an explicit confirmation in Settings.
- Audio retention is configurable per session.
- Deleting an interview removes its rows and recordings. Removing a resource profile removes the
  reusable set; documents and extraction caches remain stored locally. Global data deletion is
  planned in M9.

Never commit real personal data to this repository. Test material must be synthetic.

## License

[Apache License 2.0](LICENSE).

Some optional components run as separate programs under their own licenses. In particular, the
Piper text-to-speech engine is GPL-3.0 and runs in its own container. Model weights and voices are
downloaded by the user and keep their respective licenses.
