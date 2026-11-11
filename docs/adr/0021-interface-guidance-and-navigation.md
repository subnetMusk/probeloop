# 0021 — First-run guidance, localised page names and navigation

- Status: Accepted
- Date: 2026-11-11
- Amends: 0014

## Context

A first-time user had to discover the setup, the stages of an interview and the meaning of the
processing options alone. Breadcrumbs and tab titles showed English route slugs in an Italian
interface. On narrow screens the navigation wrapped onto several lines, and the light theme was
pure white.

## Decision

**Guidance.** Following NN/g's findings on tutorials, there is no slide-show onboarding. Instead:

- a *Getting started* checklist on the dashboard, ticked from the application's real state
  (speech components, available tools, guide opened, first interview, first report), with the next
  step's action; it can be hidden;
- a *Guide* page reachable from the navigation, with a table of contents, covering setup,
  recommended settings, each stage of an interview, privacy and troubleshooting;
- contextual help where the decision is taken: recommended tools in Settings, the reasons an
  option is unavailable, flagged answers and the background work that delays a new interview.

**Page names.** Route slugs stay English and are still the URL segments. Breadcrumbs and tab titles
(`<page name> | ProbeLoop`) show the page's name in the interface language.

**Navigation.** Wide windows show every destination and a light/dark switch (the system setting
stays in Settings). Below the `lg` breakpoint a menu button opens the destinations full screen in a
modal dialog, and the logo keeps its centred place in both states. The favicon is the two-line
wordmark drawn as outlines.

**Long pages.** Settings, the guide, reports and the accessibility statement have an "On this page"
table of contents: a sticky left rail that marks the current section on wide windows, a collapsed
list above the content on narrow ones. *Back to top* follows NN/g's guidelines: long pages only,
after scrolling back up or at the end, bottom right, as a circular arrow button with an accessible
name, and resting above the footer.

**Visual rules.** The light theme uses an off-white page, white cards and light grey surfaces, with
every text token at 4.5:1 or more on all three and input borders at 3:1. Components carry no
side accent stripes; the table of contents marker is the only edge marker.

## Consequences

- ADR 0014's rule that the breadcrumb label equals the slug no longer holds; the browser test that
  checks the tab title follows the page name.
- Guidance state (guide opened, checklist hidden) is kept in the browser only.
