# Development

The host needs Docker and git. All Python, Node, checks and builds run inside containers. Make is
an optional convenience, not an installation requirement. Use the milestone scope in the
[roadmap](roadmap.md) and the conventions in [AGENTS.md](../AGENTS.md).

## Source runtime

```bash
git clone https://github.com/subnetMusk/probeloop.git
cd probeloop
docker compose up -d --build
```

Open [127.0.0.1:8000](http://127.0.0.1:8000) and complete guided setup. The repository is currently
private, so cloning needs your normal GitHub access. No host Python or Node installation is used.
Models are downloaded through Settings; the images contain dependencies, not weights.

For hot reload:

```bash
docker compose -f compose.yaml -f compose.dev.yaml watch
```

The development overlay uses the backend dev image and Vite on `127.0.0.1:5173`, proxying API and
WebSocket requests to the backend. The runtime image serves the built SPA through FastAPI.

## Checks

Build the dev images first:

```bash
docker compose -f compose.yaml -f compose.dev.yaml build backend frontend-dev
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps -e PROBELOOP_PROVISIONER_URL= backend sh -c "ruff check . && ruff format --check . && mypy --strict -p probeloop && lint-imports && pytest"
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps frontend-dev sh -c "npm run lint && npm run lint:fsd && npm run format:check && npm run typecheck && npm test -- --maxWorkers=2 && npm run build"
```

Disabling the runtime provisioner URL in ordinary unit checks keeps their independent application
factories separate from the running machine's first-run configuration. Installation contracts
explicitly configure their own fake endpoints and synthetic files.

CI additionally runs storage contracts against disposable PostgreSQL, checks generated API types,
builds the runtime, tests missing-model startup, runs Playwright with fake engines and scans git
history for secrets. Real-model tests are marked `live` and excluded from normal CI.

## API contract

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps -v ./frontend/src/shared/api/contract:/out backend python -m probeloop.api.contract /out
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps frontend-dev npm run gen:types
```

When generating into a host bind mount, use a container UID that can write the target files.
Commit the OpenAPI documents and generated TypeScript together with the owning API changes.

## Browser acceptance

Use an isolated Compose project and data volume with `compose.test.yaml`; its model and speech
engines are scripted, while browser audio capture and Silero VAD remain real. Do not replace a
personal runtime's data volume with the test volume. CI demonstrates the supported Playwright
container invocation. The opt-in live acceptance tests need configured real tools and are not
evidence of quality merely because the scripted suite passes.

After a runtime change, rebuild the affected images and verify the actual application. Check
desktop and mobile layouts, unavailable providers, setup/download errors and a complete synthetic
interview. The real ONNX smoke helper is `backend/evals/limits_smoke.py`; its output separates
classifier timing from whole-turn latency.

## Models and release maintenance

`tools/update-model-catalog.py` rebuilds the model manifest from **pinned** upstream revisions and
their hashes. It downloads metadata and small configuration files, not the model weights. Review
changes in sources, licences, sizes and checksums before committing.

`tools/export-limits-safetensors.py` converts the final local training checkpoint and compares
every tensor. Run it in a disposable CPU torch container. Torch is not a runtime dependency;
checkpoints and exported weights stay under ignored `var/` and are published separately.

The release workflow runs CI, builds each runtime image natively for amd64 and arm64, combines
their platform manifests and creates an installer ZIP pinned to their image digests. It publishes
a prerelease rather than claiming model-quality acceptance. The ZIP contains launchers, Compose,
licence and digest metadata. Public package visibility is configured separately from the private
source repository; verify anonymous pulls before announcing a release.

Never publish dev images, data volumes, personal files, tokens or model caches as runtime artifacts.
