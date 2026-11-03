# ProbeLoop

ProbeLoop is an open-source, self-hosted platform for practising job interviews with an AI
interviewer. The interview is a spoken conversation. The interviewer asks follow-up questions
based on your answers, your CV and the job offer. After the call you get a detailed report, and
you can track your progress across sessions.

> **Status: design phase.** There is no runnable code yet. This repository currently contains
> the architecture, the initial research and the roadmap.

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
