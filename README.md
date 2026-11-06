# ProbeLoop

ProbeLoop is an open-source, self-hosted platform for practising job interviews with an AI
interviewer. The interview is a spoken conversation. The interviewer asks follow-up questions
based on your answers, your CV and the job offer. After the call you get a detailed report, and
you can track your progress across sessions.

> **Status: early development (milestone M2).** A text-only interview skeleton runs end to end;
> voice, document analysis, evaluation and the web UI come in later milestones (see the
> [roadmap](docs/roadmap.md)).

## Goals

- **A realistic conversation.** The interviewer adapts to each answer: it digs deeper, asks for
  clarification, changes topic or wraps up, and it keeps track of what has already been
  discussed.
- **Faithful transcription.** Transcripts are reviewable and correctable before evaluation.
  Correcting a transcript lets you regenerate the report without repeating the interview.
- **Honest, verifiable feedback.** The evaluator is separate from the interviewer and applies
  versioned, interview-type-specific rubrics. Every judgement cites the transcript. Scores are
  formative measures, not predictions of hiring outcomes.
- **Traceable context.** Information extracted from your CV, the job offer and public sources
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

## Running the text skeleton

**Requirements**
- Docker with Compose.
- [Ollama](https://ollama.com) on the host, with the interviewer model:

  ```bash
  ollama pull ministral-3:8b
  ```

**Start the backend.** It is published on `127.0.0.1:8000` only:

```bash
docker compose up -d --build
```

**Run a text interview** from inside the backend container. Type the answers; `/pause`,
`/resume` and `/end` control the session:

```bash
docker compose exec backend probeloop chat --type technical --language it --minutes 15
```

**Development**, with hot reload and checks inside the container:

```bash
docker compose -f compose.yaml -f compose.dev.yaml watch
```

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend pytest
```

**Tests against the real model** (`live` marker) and the interviewer evaluation:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend pytest -m live
```

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python -m evals.interviewer_personas
```

**Configuration** uses `PROBELOOP_*` environment variables
(see [settings.py](backend/src/probeloop/settings.py)). For example,
`PROBELOOP_INTERVIEWER_MODEL=qwen3.5:9b` switches the model.
`PROBELOOP_LLM_DEBUG_LOG=true` writes prompts and outputs to `/data/logs/llm.jsonl`. That log
contains personal data, so it is off by default.

## Documentation

- [Architecture](docs/architecture.md)
- [Initial research](docs/research/2026-11-initial-research.md): reuse of existing projects, local
  LLMs, speech engines and realtime transport. It distinguishes documented facts, inferences and
  points that still need to be verified.
- [Roadmap](docs/roadmap.md)
- [Architecture decision records](docs/adr/)
- [Contributor and coding-agent conventions](AGENTS.md)

## Privacy

ProbeLoop processes personal data: CVs, job offers, voice recordings and transcripts.

- All of it is stored locally in Docker volumes.
- Audio retention is configurable per session.
- Sessions and profiles can be deleted completely.

Never commit real personal data to this repository. Test material must be synthetic.

## License

[Apache License 2.0](LICENSE).

Some optional components run as separate programs under their own licenses. In particular, the
Piper text-to-speech engine is GPL-3.0 and runs in its own container. Model weights and voices are
downloaded by the user and keep their respective licenses.
