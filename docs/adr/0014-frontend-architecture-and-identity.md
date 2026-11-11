# 0014 — Frontend architecture (Feature-Sliced Design) and visual identity

> **Decision record.** Current implementation guidance is in [architecture](../architecture.md) and [configuration](../configuration.md); later ADRs amend specific decisions.

- Status: Accepted
- Date: 2026-11-08

## Context

The M6 interface grew page by page.

- **Preparation wizard.** One component owns the whole wizard. Its steps are not in the URL, so
  the browser's Back button leaves the flow and partial data is lost.
- **Pages.** Reports and transcripts mix technical data with the content the candidate needs,
  with little hierarchy.
- **Text.** Translations are an English-keyed map plus inline `it ? … : …` expressions, and
  several strings stay English in the Italian UI.
- **Owner's verdict.** In the 2026-11-08 voice acceptance review, the owner found the interface
  neither intuitive nor useful.
- **Missing features.** There is no dashboard and there are no breadcrumbs.
- **Branding.** The logo is a placeholder.

ADR 0002 already approved TanStack Query and Router, Zustand, react-hook-form, zod, Vitest,
Testing Library and MSW. Several of these were never adopted.

## Decision

**Structure: Feature-Sliced Design (FSD).**
- **Layers.** `src/` is split into `app → pages → widgets → features → entities → shared`.
  - A module imports only from lower layers.
  - Slices of one layer never import each other.
  - Every slice exposes a public `index.ts`.
- **Enforcement.** Steiger (the FSD linter) runs in CI. An ESLint rule keeps the transitional
  `src/legacy/` folder importable only from `app` and `pages`.
- **Migration.** Code that the redesign replaces moves to `src/legacy/` unchanged and is deleted
  slice by slice. Code that stays (the interview call, settings, audio, API client) moves straight
  into its layer.

**View models.**
- Reports, transcripts, fact review and chart series are built by pure, unit-tested functions,
  following the Model-View-ViewModel idea. Components only render their output: section order,
  labels, hidden technical fields and aggregates are decided in the view model.
- The interview report's section order is shared with the Markdown and PDF exports through a
  common fixture.

**State.**
- **Server state.** TanStack Query hooks per entity, with key factories. Components never call
  `fetch`.
- **Preparation draft.** The draft of a new interview is a typed, versioned Zustand store
  persisted in `sessionStorage`. It holds the settings, the profile choice, document ids and
  edits, and the preparation and snapshot ids. It is cleared when the interview starts.
- **Wizard steps.** Each step is a route, so back and forward work. Back is always allowed.
  Forward requires the step's required fields, which are marked with an asterisk.

**Navigation names.**
- Every route has an English slug that is unique across the app and identical in three places:
  the URL segment, the breadcrumb label and the tab title, written `<slug> | ProbeLoop`.
- **Static pages.** The landing page is `dashboard`; the others are `new-interview` (with the
  step slugs `interview-settings`, `resource-profile`, `documents`, `fact-review` and
  `final-check`), `interviews`, `cv-checks`, `profiles`, `settings` and `accessibility`.
- **Detail pages.** Pages that inspect one user resource use a generic slug instead of a
  per-item name: `interview-detail`, `interview-report`, `cv-check-detail`, `cv-report` and
  `profile-detail`. The URL keeps the resource id.

**Footer.** Every page except the call shows a footer with the author's attribution
(<https://github.com/subnetMusk/>) and a link to the WCAG accessibility self-assessment on the
`accessibility` page.

**Forms.** react-hook-form with zod schemas.

**Text.**
- **Dictionaries.** Typed dictionaries per slice, with English as the reference shape, so a
  missing Italian key fails the type check. Parameters and plurals are typed functions.
- **Backend messages.** Problem details from the backend are localised through one table in
  `shared/api`.
- **Retirement.** The English-keyed map and the inline language conditionals are removed slice
  by slice.

**Identity.**
- **Logo.** The wordmark is "ProbeLoop" set in Space Grotesk, with "Loop" in the accent colour.
  There is no symbol logo.
- **Favicon.** The favicon is "PL" on a rounded square filled with a violet-to-orange gradient,
  drawn as SVG paths.
- **Fonts.** Space Grotesk for headings and Inter for text, from the `@fontsource` packages,
  served by the app with no request to a font CDN.
- **Colours.** Black and white are the primary colours. Violet `#7C3AED` and orange `#EA580C`
  are accents, used for:
  - focus;
  - the current step;
  - links;
  - chart series;
  - highlights.

  Text in an accent colour uses a variant with at least 4.5:1 contrast in each theme: violet
  `#7C3AED` on light and `#A78BFA` on dark, orange `#C2410C` on light and `#FB923C` on dark.
- **Design system.** All colours are design tokens in `@theme`. Pages compose app-level
  components rather than layout classes.
- **Charts.** Hand-drawn SVG with a table alternative. No chart library.

## Consequences

- The import rules catch structural drift in CI, and the codebase has a documented place for
  every new file.
- The redesign proceeds in shippable phases while `src/legacy/` still serves the old screens.
- Fixtures shared between frontend and backend tests keep report structure consistent across the
  page, Markdown and PDF.
- New dependencies:
  - zustand;
  - react-hook-form with its zod resolver;
  - zod;
  - the two font packages;
  - Steiger with its FSD plugin;
  - Testing Library with jsdom.

## Alternatives considered

- **A simplified feature folder layout** (`app/`, `features/`, `shared/` only) — fewer rules, but
  no standard to follow and no linter.
- **Keeping one component per page** — the cause of the current problems with state and
  structure.
- **A chart library** — two simple trend charts do not justify the dependency.
- **An i18n library** — typed dictionaries cover two languages without runtime cost.
