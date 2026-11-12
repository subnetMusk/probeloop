# CV check reference labels

These labels are the reference judgements for the CV check validation set. They are defined
from the documents and this guide alone, before any output of ProbeLoop is seen, so that the
pipeline can be measured against them ([assessment of 2026-11-12](../../../../../docs/research/cv-check-assessment-2026-11-12.md)).
All documents in this directory are synthetic.

## Material

| Path | Content |
|---|---|
| `offers/<offer>.txt` | Job offers |
| `cvs/<cv>.txt` | CVs; an invariance variant is `cvs/<cv>--<variant>.txt` |
| `pairs.json` | The CV and offer of each pair, its language and, for a variant, the base pair |
| `labels.json` | The labels described below |

The reference date for open ranges ("oggi", "present") is **2026-11-12**.

## Procedure

1. The labeller receives the offers, the CVs, `pairs.json` and this guide. It never sees code,
   prompts, model output or reports of ProbeLoop.
2. The labeller writes `labels.json` with `status: draft`.
3. The owner reviews every offer, CV and pair. Each change is recorded in `review` with the path
   of the label, the value before and after, and a reason. The labeller's values stay
   recoverable, so agreement between labeller and review can be computed.
4. The reviewed file is frozen: `status: frozen` and a new `version`. A later change needs a new
   version and a reason in `changes`.

Agreement is reported as Krippendorff's alpha with bootstrap intervals: nominal for obligation,
category and coverage, ordinal for the fit band.

## Offer labels

A **requirement** is the smallest statement of the offer that a candidate can satisfy or fail on
its own. Coordinated requirements are split ("Python e PostgreSQL" gives two). Alternatives are
not split: "Python o un altro linguaggio backend" is one requirement with members.
Responsibilities ("Cosa farai", "Responsibilities") are not requirements, unless one is phrased
as a prerequisite ("devi aver già gestito...").

| Field | Values and rules |
|---|---|
| `id` | `<offer>.r<n>`, in reading order |
| `quote` | Exact text of the offer, 3 to 40 words, copied character by character |
| `category` | `skill`, `knowledge`, `experience`, `education`, `credential`, `language`, `eligibility`, `interpersonal`, `other` |
| `obligation` | `must`, `preferred` or `unclear`, by the precedence below |
| `cue` | The heading or phrase that decided the obligation; `null` for `unclear` |
| `any_of` | Members of an alternative, each `{value, open}`; an open member ("or another backend language") has `open: true` |
| `equivalents` | Alternative routes, each with `kind` (`education`, `experience`, `credential`) and `value` |
| `threshold` | `{kind: years, min, subject}`, `{kind: language_level, min}` or `{kind: degree, min}` |
| `refines` | The id of the requirement that this one narrows ("preferibilmente PostgreSQL" refines "basi dati relazionali") |
| `implicit` | `true` only when the offer's explicit text logically requires something it does not list; never inferred from the company or the sector |

**Obligation precedence.**

1. An inline cue decides. Preferred: "preferibilmente", "preferably", "gradito", "è un plus",
   "a plus", "ideally", "titolo preferenziale", "nice to have". Must: "indispensabile",
   "obbligatorio", "necessario", "required", "must", "essential", "you will need".
2. Otherwise the section heading decides. Must: "Requisiti", "Requirements", "Cosa cerchiamo",
   "What we look for", "Must have". Preferred: "Gradito", "Nice to have", "Plus", "Bonus",
   "Bonus points", "Preferred", "Costituisce titolo preferenziale".
3. Otherwise, and for every implicit requirement, `unclear`.

A preference inside a mandatory line gives two requirements: the mandatory part, and the
preferred part with `refines`.

## Pair labels

For every requirement of the pair's offer:

| Field | Values and rules |
|---|---|
| `coverage` | `direct`, `declared_only`, `partial`, `insufficient` or `contradicted` |
| `evidence` | Up to two CV quotes, best first, each with `relation` and `specificity` |
| `years` | For a years threshold: the counted years, the intervals used and their precision |
| `note` | One sentence: why this coverage |

**Coverage.**

- `direct`: the CV describes doing it in a role, project, study or volunteer activity, or states
  the credential, degree or language level. Projects and unpaid work count.
- `declared_only`: the CV only lists it (skills list, profile summary, keyword line).
- `partial`: adjacent or transferable evidence (a related tool, domain or context), or part of a
  compound requirement.
- `insufficient`: the CV shows nothing relevant. This records missing evidence, never missing
  ability.
- `contradicted`: the CV states something incompatible: fewer years than the threshold from its
  own dates, a lower language level, or an explicit limit ("nessuna gestione del cluster" against
  cluster administration). A limit contradicts only what it excludes: "nessuna gestione del
  cluster" leaves running services on Kubernetes `partial` or better.

Alternatives take the best member; equivalents take the best route. Overlapping periods count
once. A role counts towards a years threshold when its described work matches the threshold's
subject, whatever its title or technology, unless the threshold names a technology (a PHP and
Laravel role counts as backend development, not as Python). A years threshold is `direct` only
when the narrowest reading of the dates passes it, and `contradicted` only when the widest
reading stays below it; in between, the coverage is `partial` and the note says why.

**Evidence.**

- Quotes are exact CV text, 3 to 40 words, and must be found in the CV.
- `relation`: `applied` (described use), `declared` (listed), `indirect` (adjacent or
  transferable), `contradicting`.
- `specificity`: `outcome` (a result or scope is stated), `context` (role, project or period),
  `mention` (the name alone).
- Rank by relation, then specificity, then recency, then quantification.
- One quote supports several requirements only if it names each of them.
- `insufficient` has no quotes; every other coverage has at least one. `contradicted` has a
  `contradicting` quote, and `declared_only` has no `applied` one.

For the pair as a whole:

| Field | Values and rules |
|---|---|
| `target_level` | `junior`, `mid`, `senior` or `lead`, from the offer; `null` when the offer does not say |
| `fit_band` | The first that applies: `strong` when every `must` is `direct`; `weak` when a `must` is `contradicted`; `partial` when more than half of the `must` items are `direct` or `partial`; `insufficient_evidence` when every `must` is `insufficient`; otherwise `weak` |
| `rewrite_traps` | Offer terms absent from the CV; a rewrite must not introduce them |

## CV labels

| Field | Values and rules |
|---|---|
| `sections` | Each heading as written (`text`), its `type` (`profile`, `experience`, `projects`, `education`, `skills`, `languages`, `certifications`, `other`) and whether it is an extraction artefact (`artefact`) |
| `dates` | Each interval as written (`text`), with `start`, `end`, `precision` (`year`, `month`) and `open` |
| `quantities` | Each outcome or scope measure as written (`text`), with `kind` (`outcome`, `scope`); dates, phone numbers and identifiers are excluded |
| `artefacts` | Extraction artefacts (letter-spaced headings, broken lines, interleaved columns), each with a `quote` |
| `defects` | Document issues, each with `kind` (`impossible_date`, `contradiction`, `vague_wording`, `repetition`, `missing_contact`, `spelling`), a quote and `severity` (`minor`, `major`) |

A gap between periods, a missing introduction, a photo or a template is not a defect.
`missing_contact` applies only when the CV gives neither an email address nor a phone number.

## Invariance variants

A variant changes presentation only: headings renamed, sections reordered, the name changed,
the date format changed. Its coverage, evidence relations and fit band are identical to the base
pair's; only `sections`, `dates` and quote texts follow the variant. A change that alters the
evidence makes a new CV, not a variant.

## `labels.json`

```json
{
  "version": 1,
  "status": "draft",
  "reference_date": "2026-11-12",
  "labeller": "blind model labeller",
  "reviewed_by": null,
  "offers": {"<offer>": {"requirements": [{"id": "<offer>.r1", "quote": "...", "category": "experience", "obligation": "must", "cue": "Requisiti", "any_of": null, "equivalents": null, "threshold": {"kind": "years", "min": 3, "subject": "backend development"}, "refines": null, "implicit": false}]}},
  "cvs": {"<cv>": {"sections": [], "dates": [], "quantities": [], "artefacts": [], "defects": []}},
  "pairs": {"<pair>": {"target_level": "mid", "fit_band": "partial", "rewrite_traps": [], "requirements": {"<offer>.r1": {"coverage": "direct", "evidence": [{"quote": "...", "relation": "applied", "specificity": "outcome"}], "years": null, "note": "..."}}}},
  "review": [],
  "changes": []
}
```
