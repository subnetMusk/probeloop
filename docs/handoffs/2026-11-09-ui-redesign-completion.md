# M6 UI redesign verification

This checkpoint continues [the redesign handoff](2026-11-09-ui-redesign-continuation.md).
The owner authorized focused local commits only. Do not push or open a PR unless requested.
Speak Italian with the owner; keep repository text and commits in English.

## Implementation

- `6782416`: aligned dashboard grids, short lists, shared page headings, content scrolling below
  the fixed navigation and a back-to-top control.
- `ab16135`: new interview report, CV report and question/answer transcript; exact assessed
  revisions, citations, audio, corrections, refinement and report generation. Removed `src/legacy`
  and the English-keyed translation map; consumers use typed dictionaries.
- `167f87e`: pure localized report outline, Markdown/PDF parity, frozen transcript export sources,
  delivery medians and appendix, short technical hashes and primary judge reasons. JSON stays raw.
- `155b7d4`: component tests, mobile header correction, criterion bars and paginated CV versions.
- `1a522cc`: a useful narrative-summary fallback when criterion feedback is present.
- `7bc5ba9`: explicitly gated real-profile acceptance cases and synthetic PDF/DOCX fixtures.
- The README now describes the five-step flow and includes screenshots from the fake stack's
  synthetic data. Architecture documentation describes FSD, state ownership and export parity.

## Verification

- Backend: ruff lint/format, mypy strict and all nine import contracts pass. Full suite:
  **510 passed, 36 skipped, 22 deselected** (live tests excluded).
- PostgreSQL: **36 passed**, against the dedicated `pgtest` server. It initially rejected
  connections during startup recovery; the contracts passed after `pg_isready` accepted them.
- Frontend: ESLint, Steiger, TypeScript, Prettier, production build and **74 Vitest tests** pass.
  React tests use Testing Library and jsdom, alongside the pure view-model tests.
- Browser: **15 E2E tests pass** on the rebuilt fake-engine stack. The two explicitly gated live
  acceptance cases are excluded from this run. Axe found no serious or critical violations on
  the tested report, CV report and transcript pages in light and dark themes.
- Visual checks: dashboard at 1280 and 1440 pixels in both themes; report and transcript at
  390 pixels; PDF output inspected page by page after rendering with Poppler. Mobile metadata
  originally became too narrow beside actions and was corrected before the final E2E run.
- The shared synthetic `report-outline.json` pins the section order, notes, evidence numbering,
  primary reasons, requirement coverage, medians and technical fields in pytest and Vitest.
  Component tests also compare the actual DOM order with the contract.
- Restore: built a synthetic schema-`0003` archive with one profile and one resource. The runtime
  CLI restored it into an empty `/data` tmpfs in `probeloop-restore-acceptance`, then HTTP verified
  the upgraded profile and resource and null CV/offer fields. The temporary container was removed.
  **The primary volume was never used for delete-all or restore tests.**

## Real-stack acceptance

The backend was rebuilt and restored with `docker compose up -d --build backend`. It is healthy,
mounts **`probeloop_data` at `/data`**, and has both fake-engine flags disabled. The default remains
the ChatGPT plan and plan usage is enabled. Tests choose the profile per interview and do not
change that default or the account.

**Both opt-in real-profile acceptance cases passed** (local: 7.2 minutes; cloud: 4.2 minutes).
Each uploaded the synthetic PDF CV and DOCX offer through the five-step flow, reviewed the
context, generated a CV report with original-file preview, recorded one voice answer, refined
its transcript and generated/exported an interview report. Both answers have retained audio and
a nonempty `retranscription` revision. No account setting was changed and no bot check was bypassed.

| Profile | Session | Interview report | Model | Assessable criteria |
|---|---|---|---|---|
| Local | `01a1c0e00692795a8af436650b278198` | `01a1c0e2a0a67a2b98bca399732ea55d` | `ollama:qwen3.5:9b@ctx16384` | 1/5, no overall score |
| ChatGPT plan | `01a1c0e436f274cca3262223dd8b8fc8` | `01a1c0e678a778a8bbfd86e184f222a4` | `chatgpt:gpt-6.1-terra` | 3/4 |

The local CV check rejected eight generated items and left 0/7 criteria assessable; the cloud
CV check assessed 7/7. The local interview also classified its answer as hypothetical despite the
HR question. These are observed M7 model-quality limitations, not a calibration pass. The UI
correctly preserves missing scores and the source transcript rather than inventing evidence.
The synthetic microphone stream was cut to a short answer, and the recogniser made mistakes;
its doubtful words are highlighted. A real user should review them before requesting assessment.

CV report references: local `01a1c0dfad3e70aba69b73997d933438` (144.33 seconds), cloud
`01a1c0e4191b739488a6c87c4a1111dc` (36.96 seconds). Interview reports took 51.82 and 40 seconds
respectively. These timings describe this short synthetic run, not general latency targets.

The rebuilt real dashboard, both transcripts/reports and both PDF previews were inspected. The
default Chromium headless shell showed an empty PDF frame despite correct `application/pdf`
and inline headers; a read-only check with `chromium.launch({ channel: 'chromium' })` rendered
the complete original PDF in both CV reports. Native PDF preview requires that full browser
for visual QA. Runtime screenshots remain under ignored `var/ui-redesign` and
`frontend/test-results`; only screenshots containing synthetic data are committed in docs.

The real CV report also exposed a misleading empty-summary message when criterion feedback was
present. The fallback now invites the reader to explore the evidence below, with component
coverage; the unavailable-overall-score case retains its explicit explanation.

## Commands and remaining cautions

Run checks in containers. The dev backend image may contain older source; mount `backend` at
`/app`. Frontend checks must see the repository root because tests read the backend fixture:

```powershell
docker run --rm -v C:/Users/SOS/Desktop/git_projects/ProbeLoop:/repo -w /repo/frontend node:24.22.0-trixie-slim sh -c 'npm ci && npm run lint && npm run lint:fsd && npm run format:check && npm run typecheck && npm test && npm run build'
```

A named volume at `/repo/frontend/node_modules` avoids slow dependency reads from the Windows
bind mount. The development frontend image and Compose watch also include the shared fixture.
After API changes regenerate the contract first, then the frontend types; CI checks drift.

```powershell
docker run --rm --network container:probeloop-backend-1 -e PROBELOOP_LIVE_ACCEPTANCE=1 -v C:/Users/SOS/Desktop/git_projects/ProbeLoop:/repo -w /repo/frontend mcr.microsoft.com/playwright:v1.65.0-noble npx playwright test e2e/live-acceptance.spec.ts
```

`live-acceptance.spec.ts` only adds synthetic records. It never deletes data or changes account
settings. Its fixtures can be rebuilt with
`backend/tests/fixtures/synthetic/context/generate_ui_documents.py` inside the dev container.

- Rebuild before verifying runtime changes. Fake E2E runs use `probeloop_e2e_data`; restore and
  inspect the real mount afterwards.
- Theme scans wait for finite transitions to settle; scanning halfway through a color transition
  creates transient contrast failures.
- Wait for all history queries before capturing the dashboard; counts can still be loading when
  its interview rows first appear.
- Lists and versions are newest first and paginated; never assume a fixed report version on the
  persistent E2E volume.
- Keep model-generated technical feedback qualified. A matching quotation verifies its source,
  not the truth of the claim. Dynamic unknown server messages can still be English.
- WCAG 2.2 AA remains a self-assessment, with limitations on `/accessibility`.
- Vite still warns about the main bundle exceeding 500 kB. No chart library or later-milestone
  features were added to address that warning.
- Never log or commit tokens or real documents. Never bypass Cloudflare or another bot check.

The older model/voice/retention settings, ModelCatalog and diagnostics proposals are outside this
approved redesign. Separate M7 model calibration work remains recorded in the earlier assessment
handoff; do not infer that a finished UI closes it.
