# UI redesign (M6) continuation

> **Historical checkpoint.** This records the state and checks at its original date. Later changes may supersede it.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

Historical starting checkpoint. See [the verification checkpoint](2026-11-09-ui-redesign-completion.md)
for the continuation work and final acceptance status.

This is a development checkpoint of the redesign that the owner requested on 2026-11-08: a
linear preparation flow, CVs and job offers in profiles, a dashboard, new reports and
transcripts, and a new visual identity. Read `AGENTS.md`, this document,
[ADR 0014](../adr/0014-frontend-architecture-and-identity.md) and
[ADR 0015](../adr/0015-execution-profile-per-interview.md) before continuing. The approved plan
is also kept outside the repository at `C:\Users\SOS\.claude\plans\tidy-soaring-cascade.md`;
everything needed from it is summarised below.

Speak Italian with the owner. Code, comments, documentation and commit messages are English.

## Working rules

- **Commits.** Local commits are authorised without asking. Each commit is focused, with an
  imperative subject of at most 72 characters and a body that explains why.
- **No attribution, no push, no PR.** Never add AI attribution (`Co-Authored-By`, "Generated
  with"). Never push and never open a PR unless the owner asks; do not suggest pushing either.
  A push request covers the work done up to that moment, once.
- **Verify outside tests.** Green suites are not enough. Check the running app in a browser
  after behavioural changes, and rebuild images, bundles or lockfiles before verifying them.
  Capture exit codes before piping output into `grep`, `head` or `tail`.
- **Data.** Test material is synthetic and lives under `fixtures/synthetic/`. Never commit real
  CVs, transcripts, recordings, tokens or `.env` files. Never test delete-all on the primary
  data volume `probeloop_data`. ChatGPT tokens stay in the data volume: never log them, put them
  in URLs or send them to the browser. Do not bypass Cloudflare or other bot checks.
- **UI quality bar** (owner feedback). Pages must be pleasant, modern and easy to use:
  - no endless lists: newest first, short pages with previous and next;
  - longer lists only on dedicated pages, and only when nothing follows them;
  - cards side by side must line up in width and height;
  - required fields marked with `*`; Back always allowed and keeps the data; Continue disabled
    with a hint naming what is missing.

## Owner decisions

| Topic | Decision |
|---|---|
| Architecture | Full Feature-Sliced Design (`app → pages → widgets → features → entities → shared`), checked by Steiger. Pure, unit-tested view models feed the pages. Remaining old screens live in `src/legacy`; only `app` and `pages` may import them (ESLint rule). |
| Identity | A typographic wordmark, Space Grotesk for headings and Inter for text (`@fontsource-variable`). Black and white, with accents violet `#7C3AED` and orange `#EA580C`. The favicon is "PL" on a rounded square with the accent gradient. |
| Navigation names | English slugs, unique, identical in the URL, the breadcrumbs and the tab title `<slug> \| ProbeLoop`. Detail pages use generic slugs: `interview-detail`, `interview-report`, `cv-check-detail`, `cv-report`, `profile-detail`. |
| Footer | Attribution to subnetMusk (https://github.com/subnetMusk/) and a WCAG 2.2 AA self-assessment page at `/accessibility`. |
| Execution profile | Chosen per interview in step 1: local (Ollama) or ChatGPT plan (Sign in with ChatGPT, OAuth, never an API key). The interviewer, analysis, CV check and reports of that preparation or interview use it. Speech recognition and synthesis always run locally. |
| Preparation flow | `/new-interview/{interview-settings, resource-profile, documents, fact-review, final-check}`. The draft persists in `sessionStorage` until the interview starts. A later step opens only when the earlier ones are complete. |
| Fact review | A dedicated step with a compact summary. Only doubtful facts are open (inferred, or from documents with warnings); a green check confirms and a red X excludes. The full list is collapsed. Changing an approved review reopens it. |
| Profiles | Hold a CV, a job offer and resources. Changed documents of a saved profile prompt to overwrite it, save as a new profile, or use them once. CV checks and profiles have their own detail pages (D2). |
| D1, trends | Overall-score lines join points with the same `scorer_key` (rubric, model, prompt, language) and the same interview type; a change of evaluator starts a new run. |
| D3, edits | Editing an uploaded document creates an `EDITED` revision that keeps the original file downloadable. |
| D4, CV check language | The interview language from step 1; there is no language selector in the step. |
| Prompts | Keep prompts short and provider-neutral. Small-model mitigations go in code, not in prompt wording. |
| Charts | Hand-drawn SVG, no chart library. Series colours follow the interview type, in a palette validated for colour-vision deficiencies against the card surface: light `#7c3aed, #ea580c, #1baf7a, #2a78d6`; dark `#9d7bf5, #ea580c, #199e70, #3987e5` (`--chart-1..4`). Every chart has a legend for two or more series and a table view. |

## State

### Committed (local)

| Commit | Content |
|---|---|
| `0f6cfa1` | ADRs 0014 and 0015 |
| `92708c3` | FSD move |
| `5e3cef2` | Typed message dictionaries (`defineMessages`, `useMessages`) |
| `0626643` | Identity, slugs, breadcrumbs, footer |
| `a75292b` | Restore of backups taken at earlier schema revisions |
| `14e920a` | CV and job offer in profiles; migration `0004` |
| `2e92bf0` | `GET /api/documents/{id}/original` |
| `c8cbf7e` | Execution profile per preparation and interview; migration `0005` |
| `f764256` | `POST /api/preparations/{id}/reopen`, extended `SnapshotView`, `/api/history/interviews`, `/api/history/cv-checks`, and `/api/progress` with CV reports, `scorer_key` and `interview_type` |
| `559bd21` | The five-step preparation flow; the legacy setup was removed |
| `52383ea` | Dashboard, `/interviews`, `/cv-checks`, `/cv-checks/$snapshotId`, `/profiles`, `/profiles/$profileId` |

### Not committed

**1. Layout corrections requested by the owner.** These pass lint, typecheck, Steiger, Prettier
and the unit tests (64). They are **not yet verified** by E2E or in the browser.

- **Scrolling.** The header stays in place and only the content below it scrolls
  (`widgets/app-shell/ui/layout.tsx`, `data-testid="content"`). The content area returns to the
  top on every route change.
- **Back to top.** A round button with an up arrow, bottom right, outside the 72rem column
  (`back-to-top.tsx`). It appears after scrolling and scrolls smoothly.
- **Page headers.** A shared `PageHeader` and `Page` (`shared/ui/page-header.tsx`) give every
  page a heavier title in one place. All pages use one 72rem column (`max-w-6xl`).
- **Dashboard grid.** Four KPI tiles, then two equal trend cards with the same internal
  structure, then three equal lists of 4 rows. List rows have a fixed height (`ROW_HEIGHT`), the
  list keeps room for a full page, and the pager sits at the bottom of the card.
- **E2E types.** `tsconfig.node.json` now includes the `DOM` lib, because end-to-end code runs
  in the page.
- **Dashboard E2E.** `e2e/dashboard.spec.ts` expects 4 rows per page and covers the back-to-top
  button.

**2. Start of Phase 3.** `entities/report/model/report-view.ts` holds `toInterviewReportView` and
`toCvReportView`, with tests (passing). They implement the reading order below: answers
numbered as the candidate gave them, one reason per judge, each note once, and delivery
medians.

### Runtime state at handoff

`probeloop-backend-1` was started with the **test overlay**: fake engines and the volume
`probeloop_e2e_data`. Before using the real app, restore it:

```powershell
docker compose up -d --build backend
```

Then check that the container mounts `probeloop_data`. The PostgreSQL test container `pgtest`
is stopped; start it with `docker start pgtest` (network `pgtest`). If it is missing, create it
as CI does in `.github/workflows/ci.yml`.

## Remaining work, in order

### 1. Verify and commit the layout corrections

1. Run the frontend checks.
2. Rebuild the test image and run all E2E tests (11 before this change).
3. Look at `/dashboard` at 1280 and 1440 px wide, in light and dark themes. The cards must
   line up, only the content may scroll, and the back-to-top button must stay outside the
   content.
4. Commit, for example `fix(frontend): align the dashboard and scroll below the header`.

### 2. Phase 3: reports and transcripts

These pages replace the remaining legacy screens.

**Interview report** (`/interviews/$sessionId/reports/$reportId`), in this order:

1. Header: type, date, duration and execution-profile chip. Take them from
   `interviewHistoryQuery`, which has `effective_s`.
2. Hero: overall score, band and summary.
3. "What to improve": priorities first. Technical errors are highlighted with their correction
   (`replacement`). Each note shows its "Question N" block and quotes as "Answer N" links.
4. Strengths.
5. Question by question: one card per unit, with:
   - the questions as text;
   - the answers as assessed, with audio;
   - compact criterion bars with the first reason;
   - logistics and unclassified units marked as not scored.
6. Job requirements: what the interview touched next to what the documents show.
7. "How you spoke": median pace, median latency, fillers per minute, long pauses, talk share and
   budget share. The per-answer table is collapsed.
8. A collapsed "Technical details": model, prompt, rubric, short hashes, discarded items,
   edited answers and the disclaimer.

Exports (MD, JSON, PDF), the recording and the transcript are linked from the header. The
interview's session (`api.session`) supplies the question texts and audio.

**CV report** (`/cv-checks/$snapshotId/reports/$reportId`): hero, criteria with reasons, the
requirement matrix against the offer, and the deterministic checks as a checklist (review, then
info, then pass, then not assessable). Then suggestions and rewrites, questions to practise, and
the original file. Use `api.snapshot` with `RequirementList` from `entities/preparation`.

**Transcript page** (`/interviews/$sessionId`):

- Page header with the metadata and actions (latest report, transcript downloads, recording).
- A banner for the refinement state (`api.refine`, job `refine_transcript`).
- Report generation (`api.reviewInterview`, job `review_interview`, `rememberReportJob`).
- The conversation as question-and-answer blocks. Each answer has its audio, "Correct" and its
  revision history. Words with probability below 0.5 stay highlighted.
- A two-column layout with a sticky aside fits.

**Then:**

- Delete `src/legacy` and its router imports, the ESLint `@/legacy` rule and the Steiger ignore.
- Migrate the remaining `localise`, `<T>` and `IT` uses (`shared/i18n/legacy.ts`) to typed
  dictionaries, then delete the legacy map.
- Update `e2e/voice-interview.spec.ts`. It relies on these legacy names:
  - test ids `refine-done`, `answer-text`, `interview-report-panel` and `report-content`;
  - buttons "Correct", "Save correction" and "Generate report";
  - the field label "Corrected answer";
  - the links `/^Open report v1 /` and "MD", "JSON", "PDF";
  - the quote `“Ho lavorato con FastAPI”`.

  Keep them where they still make sense, or update the spec.

### 3. B6: report outline and exports (backend)

- **`paired_scores`** (`assessment/domain/units.py`): keep only the primary reason.
- **`assessment/application/outline.py`:** a pure `report_outline(report, questions)` in the same
  section order as the page, with localised labels (`labels.py`) and the delivery summary.
  Hashes are shortened to 8 characters and appear only in the technical block.
- **Exports:** Markdown and `report.html.j2` (PDF) render the outline. The per-turn delivery
  table goes in an appendix. The unstable-score footnote appears only when some score is
  unstable. JSON stays the raw `ReportData`. Use brand colours in the PDF CSS.
- **Parity fixture:** `backend/tests/fixtures/synthetic/assessment/report-outline.json`, checked
  by pytest against the outline and by Vitest against the frontend view model, so the two
  orders cannot drift apart.

### 4. Phase 5: wrap-up

**Tests:**

- Component tests with Testing Library. Vitest currently includes only `src/**/*.test.ts`; add
  `*.test.tsx` and the `jsdom` environment.
- Axe scans of the report and transcript pages.

**Docs:** the README (new flow, screenshots), `docs/roadmap.md` (M6), the frontend section of
`docs/architecture.md`, and a new handoff.

**Final verification on the real stack:**

1. One short voice interview per execution profile, local and ChatGPT plan, through the new flow,
   with an uploaded PDF and DOCX.
2. The report, a CV check with the file preview, and screenshots of the dashboard, the report and
   the transcript.
3. Restore a backup made before migration `0004` into an empty instance.

## Commands (Windows, Git Bash)

The `probeloop-backend:dev` image contains an old copy of the source. Mount the working tree
instead of relying on it. Prefix `docker run` with `MSYS_NO_PATHCONV=1`.

Backend checks:

```bash
docker run --rm -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/backend:/app' probeloop-backend:dev sh -c 'ruff check src tests evals && ruff format --check src tests evals && mypy && lint-imports && pytest -q -p no:cacheprovider'
```

Storage tests on PostgreSQL:

```bash
docker run --rm --network pgtest -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/backend:/app' -e PROBELOOP_TEST_DATABASE_URL=postgresql+asyncpg://probeloop@pgtest:5432/probeloop_test probeloop-backend:dev pytest -q -p no:cacheprovider tests/storage -k postgresql
```

API contract and frontend types, after any API change:

```bash
docker run --rm --user 0 -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/backend:/app' -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/frontend/src/shared/api/contract:/out' probeloop-backend:dev python -m probeloop.api.contract /out
```

```bash
docker run --rm -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/frontend:/work' -w /work node:24.22.0-trixie-slim npm run gen:types
```

Frontend checks. The host Node.js is too old, so always use the container:

```bash
docker run --rm -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop/frontend:/work' -w /work node:24.22.0-trixie-slim sh -c "npm run lint && npm run lint:fsd && npm run typecheck && npm test && npx prettier --check . && npm run build"
```

End-to-end tests run against fake engines on the `probeloop_e2e_data` volume:

```bash
docker compose -f compose.yaml -f compose.test.yaml build backend
```

```bash
docker compose -f compose.yaml -f compose.test.yaml up -d --no-deps backend
```

```bash
docker run --rm --network container:probeloop-backend-1 -v 'C:/Users/SOS/Desktop/git_projects/ProbeLoop:/repo' -w /repo/frontend mcr.microsoft.com/playwright:v1.65.0-noble npx playwright test
```

Afterwards, restore the real backend on `probeloop_data`:

```bash
docker compose up -d --build backend
```

The app runs at http://127.0.0.1:8000.

## Pitfalls already met

- **Bash heredocs.** They break on typographic apostrophes (`’`) and on `\\` escapes. Write Python
  edit scripts to a file and run them with `python -I <file>`.
- **Required marks.** `getByLabel(name, { exact: true })` does not match labels that carry the `*`
  mark. Use `getByRole('textbox', { name, exact: true })`; the mark is `aria-hidden`.
- **The E2E volume keeps data between runs.** Seed what a test needs through the API, and never
  assume counts or the first version of a report.
- **Hidden elements.** Playwright treats `opacity: 0` as visible. Hide with `invisible`.
- **Contrast.** Muted text on `bg-muted` fails 4.5:1; use `text-foreground/75`. Do not tint or fade
  cards that contain muted text.
- **Breadcrumbs.** Their links use `activeOptions={{ exact: true }}`, so that only the last crumb
  has `aria-current`.
- **Overlay labels.** `ChoiceCard` stretches its label over the card; the radio sits above it
  (`relative z-10`), or Playwright cannot click it.
- **Prettier.** It can fail with `EINVAL` on the Windows bind mount; run it again.
