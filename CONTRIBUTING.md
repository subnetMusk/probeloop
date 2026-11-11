# Contributing

ProbeLoop is in early development. Start with the [current status](docs/status.md),
[roadmap](docs/roadmap.md) and [architecture](docs/architecture.md).

The contributor rules in [AGENTS.md](AGENTS.md) apply to people and coding agents. Use English
for identifiers, comments, documentation and commit messages. Keep dependencies pointed toward
plain domain/application code; wire concrete adapters only in `bootstrap`.

Use the [container-based development guide](docs/development.md). Behaviour changes require
appropriate tests and verification in a rebuilt running application. Real-model tests are
marked `live` and excluded from ordinary CI.

Use synthetic fixtures only. Never commit credentials, personal documents, recordings,
transcripts, model weights or `.env` files. Describe the problem, resulting behaviour, checks
and any remaining acceptance limits in a focused contribution.
