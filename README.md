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

Then open <http://127.0.0.1:8000>, check the microphone, and join. Joining loads the language
model and the speech engines first, which can take a minute the first time. Use headphones if you
can: the microphone only records between "Answer" and "End of answer" (or the space bar), but
headphones keep the interviewer's voice out of the room.

**Prepare the context first.** Upload or paste your CV and, optionally, a job offer. You can also
describe a role, edit the generated offer, or choose a getting-to-know interview without an offer.
Add titled resources (text, Markdown, JSON, XML, HTML, DOCX or PDF), choosing an existing profile
or saving a new one. Changed profiles can be overwritten, copied or used for this interview only.
Documents are analysed asynchronously with `qwen3.5:9b` (download it with `ollama pull qwen3.5:9b`).
Review, correct or exclude the extracted facts and confirm the inferred area without an offer.
Approval freezes the context used by the interviewer and the refinement vocabulary. No document
link is followed. A quick start without documents remains available.

**After the call** your answers are transcribed again from their recordings with Whisper, a
slower but more accurate recogniser (a few minutes for a 10-minute interview; the first run also
loads the model). "Your interviews" lists past sessions: each has the recording, the transcript
with the doubtful words highlighted, and the downloads. Correcting an answer keeps the earlier
versions.

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
docker run --rm -v "$PWD/frontend:/work" -w /work node:24.22.0-trixie-slim sh -c "npm ci && npm run lint && npm run typecheck && npm test && npm run build"
```

**API types.** The frontend's TypeScript types are generated from the backend's contract (OpenAPI
and the JSON Schema of the WebSocket messages); CI fails when they are out of date:

```bash
docker run --rm -v "$PWD/frontend/src/api/contract:/out" probeloop-backend:dev python -m probeloop.api.contract /out
```

```bash
docker run --rm -v "$PWD/frontend:/work" -w /work node:24.22.0-trixie-slim npm run gen:types
```

**End-to-end test.** Playwright drives Chromium with a fake microphone against a backend that uses
a scripted interviewer and fake speech engines (no GPU or models needed):

```bash
docker compose -f compose.yaml -f compose.test.yaml up -d --no-deps backend
```

```bash
docker run --rm --network container:probeloop-backend-1 -v "$PWD:/repo" -w /repo/frontend mcr.microsoft.com/playwright:v1.65.0-noble sh -c "npm ci && npx playwright test"
```

Run `docker compose up -d --no-deps backend` afterwards to go back to the real engines.

**Tests against real models** (`live` marker): the interviewer with Ollama, and the speech engines
in-process and through the running services:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm -e PROBELOOP_TEST_STT_URL=http://stt-worker:8000 -e PROBELOOP_TEST_TTS_URL=http://tts-piper:5000 backend pytest -m live
```

**Evaluations.** The interviewer with scripted text personas:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python -m evals.interviewer_personas
```

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

- All of it is stored locally in Docker volumes.
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
