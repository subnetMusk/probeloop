# CV check assessment: baseline, literature and classifier measurements (2026-11-12)

> **Research and validation record.** Interpret measurements in their original conditions; they are not current runtime guarantees.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

The owner reviewed the CV check and raised six points: semantic matching and scoring (P0), evidence
selection, document analysis and internal consistency (P1), and feedback (P2). This record checks
each point against the code at commit `81c13e1`, collects published practice for each area and
assesses a fast classifier layer (Jev now, Laya later). The baseline precedes changes to the
pipeline; the Jev section records the later classifier measurements.

The baseline called no real model. A probe feeds synthetic material to the deterministic steps
and to the reviewer with scripted model outputs; it shows what the code accepts, not how often
a real model produces such output. At that checkpoint no reference judgements existed, so none
of the six areas had a measured error rate.

## Method

- **Code.** The analysis (`context/application/analysis.py`, prompts `extract_facts.v1` and
  `match_requirements.v1`), the target brief (`context/application/snapshots.py`), the review
  (`assessment/application/cv_review.py`, `evidence.py`, `cv_checks.py`, `schemas.py`, prompt
  `review_cv.v2`, rubric `cv.v1`), the aggregation and the CV report widget.
- **Probe.** `backend/evals/cv_check_probe.py` uses the acceptance CV and the PagaFacile offer in
  `backend/evals/fixtures/synthetic/context/acceptance/`. Its output is deterministic:

  ```bash
  docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps -e PROBELOOP_PROVISIONER_URL= backend python -m evals.cv_check_probe
  ```

- **Requirements.** The [CV rating requirements](../proposals/2026-11-cv-rating-guidelines.md),
  [section 3 of the context proposal](../proposals/2026-11-context-evaluation-reports.md#3-cv-review-new)
  and the earlier [CV review measurements](cv-review-results.md).
- **Literature.** Sources carry an access label: *full text*, *abstract* (the abstract or landing
  page was read) or *snippet* (search summaries only; check the original before relying on a
  number). The three most recent preprints were re-read at abstract level on 2026-11-12.

## Pipeline at the baseline

The analysis splits each document into passages of at most 3,500 characters and asks the model
for at most 25 facts per passage. Each fact has a subject, a kind, a one-sentence statement and a
quote. A second call compares requirement statements with candidate statements and returns `met`,
`partial` or `not_shown` per requirement. The user then confirms a role profile.

The review splits the CV into passages of at most 3,000 characters. One call per passage scores
all seven `cv.v1` criteria from 1 to 5 or `null`, with up to two quotes each and up to five
observations. Code verifies quotes, drops URL-only evidence and rewrites that add digits, then
averages each criterion over passages. The overall score is the equal-weight mean of the
available criteria when at least 60% are assessed. Deterministic checks run beside the model and
appear as a separate report section.

## Findings by critique point

| Point | Verdict | Main evidence |
|---|---|---|
| P0 semantic matching | Confirmed | No obligation, alternative or threshold structure; reviewer does not see requirement kinds or match statuses |
| P0 scoring calibration | Confirmed | One mean of five document criteria and two fit criteria; bands in code; passage means hide disagreement |
| P1 evidence selection | Confirmed | One skills-list quote validates all seven criteria; no ranking or directness |
| P1 document analysis | Confirmed for the deterministic checks, partly for ATS claims | Exact headings, year-only dates, narrow units; layout claims are already restricted |
| P1 internal consistency | Confirmed | No validation step; a match status contradicts its own rationale |
| P2 feedback | Confirmed | Observations unlinked and unprioritised; rewrite guard checks digits only |

### P0: semantic matching

- **Requirements have no structure beyond two kinds.** An extracted fact has `subject`, `kind`,
  `statement` and `quote` (`analysis.py:64-70`). Offer facts are `requirement`, `nice_to_have`,
  `responsibility` or `company` (`extract_facts.v1.j2:16`). Obligation cues, alternatives ("Python
  or another backend language"), preferences inside a requirement ("preferably PostgreSQL"),
  equivalences and thresholds ("at least three years") are kept only as free text (probe §2).
- **Uncertain kinds become hard requirements.** An offer fact returned with a candidate kind is
  stored as `requirement` (`analysis.py:343-345`; probe §2: `skill` became `requirement`).
- **Matching reads summaries, not the CV.** The match call receives requirement statements and
  candidate statements only (`analysis.py:378-381`). The extraction prompt prefers "the facts an
  interviewer would ask about" within its 25-fact cap (`extract_facts.v1.j2:22`). A skill that
  appears only inside a project description is matched only if the extractor named it in a
  statement. This is structural; it was not measured with a real model.
- **Declared and applied skills are not distinguished.** Candidate kinds exist (`skill`,
  `project`, `role`), but a match records only fact ids and a rationale, and the requirement view
  lists supporting statements (`context_routes.py:271-279`). Nothing tells a skills-list entry from
  a described use.
- **The reviewer does not see the requirement table.** With a confirmed role profile, which every
  new preparation has, the target brief is the profile plus selected job facts printed without
  their kind or match status (`snapshots.py:126-137`, `snapshots.py:222-223`; probe §4). Without a
  profile, preferred items are listed under "Requirements the candidate's documents do not show"
  next to mandatory ones (`snapshots.py:153-168`; probe §4). The proposal expected relevance to be
  judged "against the requirement matrix".
- **Absence wording is right, its mechanics are not.** Statuses say `not_shown` ("Non
  dimostrato"), as the requirements ask. A requirement the model omits becomes `not_shown` with an
  empty rationale, and a `partial` supported only by an inferred fact becomes `not_shown`
  (`analysis.py:424-433`; probe §3). The review then scores each passage on relevance, so a passage
  without relevant content lowers the criterion (see P0 scoring).

### P0: scoring calibration

- **Document quality and job fit share one number.** The overall score averages all assessed
  criteria with equal weights (`domain/model.py:144-149`). Five of the seven `cv.v1` criteria
  describe the document (impact, ownership, clarity, consistency, readability) and two describe
  fit (relevance, depth). Trends and history show this single value.
- **Anchors are generic.** Each criterion has anchors at 1, 3 and 5; levels 2 and 4 are "between
  anchors" (`cv.v1.yaml`, `review_cv.v2.j2:7`). "Depth for the target level" refers to the
  confirmed level without describing what any level requires (`cv.v1.yaml:36-41`).
- **Thresholds live in code, not in the rubric.** Bands are `solid` from 4, `developing` from
  2.5 (`outline.py:179-188`; `report-view.ts:35-40` on the 0-100 scale). They are fixed and tested
  but not tied to the anchors or to seniority, and they are not versioned with the rubric.
- **Passage means hide disagreement.** In probe §6 one passage scores relevance 5 and two score
  1; the criterion becomes 2.33 and its reason concatenates "Strong evidence for the target" with
  "Little evidence for the target here" (`cv_review.py:91-106`). The 2026-11-08 measurements
  already noted that chunk-level means can lose cross-passage context.
- **Uncertainty is binary.** A criterion is a number or `null`, and the report shows how many
  criteria were assessable. Disagreement between passages, quote failures and run-to-run variation
  are not shown. Aggregation is deterministic; the labels come from one model call at temperature
  0.1 per passage.
- **Depth that only an interview can show is rated from the CV.** The prompt says missing
  evidence is not missing ability (`review_cv.v2.j2:11`), but the level-1 anchor for depth is
  "little detail about work expected at the confirmed target level", which a concise CV meets.

### P1: evidence selection

- **Any verified quote validates any score.** A score survives when at least one of its quotes
  (at least 8 characters) is found in the passage (`evidence.py:104-117`). In probe §5 the quote
  "Python, FastAPI, Django, SQLAlchemy, PostgreSQL" supports a 5 on all seven criteria, including
  impact and ownership. The requirements ask for a quote "that supports its reasoning, not merely a
  quote containing a matching keyword".
- **No ranking, directness or reuse control.** The schema allows two quotes per criterion
  (`schemas.py:70`); passages add theirs to the union (`cv_review.py:104`). Relevance,
  specificity and probative strength are not recorded, and the same span may support every
  criterion.
- **A reason can outlive its evidence.** When one of two quotes fails verification, the score and
  the model's reason are kept with the remaining quote (`evidence.py:106-116`); the reason may
  describe the dropped one.

### P1: document analysis

- **Headings are exact strings.** Section checks match whole lines against a few Italian and
  English names (`cv_checks.py:18-24`). A colon, "PROFESSIONAL EXPERIENCE", "Work history", a
  letter-spaced extraction ("E S P E R I E N Z E") or "Progetti" turn the experience check to
  `review` (probe §1). The detail says that the content may still be present, which follows the
  requirements' wording; recognising variants, as the requirements ask, is not implemented.
- **Dates are year ranges only.** The chronology check reads `YYYY - YYYY` (`cv_checks.py:11`).
  "2022 - oggi", the candidate's current role, is ignored; with month-year ranges no range is read
  and gap or overlap checks are silent (probe §1).
- **Quantification misses common units.** On the acceptance CV the check finds "1.800 consegne"
  and "12 minuti" (`cv_checks.py:12-16`). It misses "35 operatori", the "40" of "da 40 a 12
  minuti", "1,4 s" and "380 ms".
- **Extraction artefacts are not separated from CV defects.** Only PDF hidden-text warnings reach
  the report; letter spacing, broken lines or split metrics are not detected.
- **ATS claims are already limited.** Layout and link reachability are `not_assessable`
  (`cv_checks.py:131-152`) and the prompt confines readability to local extracted text
  (`review_cv.v2.j2:14`). This part of the critique is contradicted by the code; no model
  observation is checked against it, though.
- **Deterministic and semantic results are not reconciled.** The model does not receive the
  checks, and nothing compares them, so a "heading not recognised" check can sit next to a model
  observation that praises the structure.

### P1: internal consistency

- **No validation step exists.** The reviewer's verified output becomes the report directly
  (`service.py:225-262`).
- **A status can contradict its rationale.** Probe §3 stores `not_shown` with the rationale "Usa
  Kafka: copertura parziale"; the requirement view shows both (`analysis.py:428-434`).
- **Two fit judgements run independently.** The requirement table comes from the analysis; the
  relevance score comes from the review, which does not see the table. The report shows them in
  separate sections (`cv-report.tsx:17-22`) and nothing checks that they agree.
- **Passage outputs are concatenated.** Reasons are joined and observations repeated: probe §6
  returns "Quantify outcomes." three times.

### P2: feedback

- **Suggestions are unlinked and unprioritised.** CV observations have a kind, a text, quotes and
  an optional replacement, but no criterion or requirement (`schemas.py:92-96`). Each passage adds
  up to five, without deduplication or a synthesis step; interview reports have one, CV reports do
  not.
- **Rewrites and requests for information share one list.** Kinds are `strength`, `improvement`,
  `rewrite` and `question`; a fix the candidate can make by rewording is not told apart from a
  detail only the candidate can supply.
- **The rewrite guard checks digits only.** A rewrite is dropped when it adds a number absent from
  its quotes (`evidence.py:126-131`). Probe §5 keeps "Ho guidato il team backend e gestito
  Kubernetes in produzione" for "Affianco due sviluppatori junior nelle revisioni del codice", and
  "dodici corrieri internazionali" for "tre corrieri".

### Evaluation basis

`backend/evals/cv_review.py` runs one CV without an offer (`JobMode.NONE`) on Ollama and writes
the output without comparing it with expected judgements (`cv_review.py:34-49`). The labels in
`fixtures/synthetic/context/labels.json` cover fact quotes and terms, not obligation, coverage or
scores. The synthetic cases listed in the requirements exist as unit tests of code guards with
scripted outputs (`backend/tests/assessment/test_cv.py`), not as a labelled set for a real model.

## Literature

### Matching and screening with LLMs

LLM résumé scores correlate weakly with human ratings: on 736 real résumés, zero-shot GPT-4
scores agreed poorly with human ones, and chain-of-thought prompting helped [1]. Presentation
changes with the same qualifications reversed 29.6% to 41.4% of pairwise screening decisions
across models, and validity and stability were largely unrelated [2]. Models prefer résumés they
wrote (67% to 82%), so a rewrite rescored by the same model is not evidence of improvement [3].
Pairwise comparisons favour the first-listed candidate; scoring one CV at a time removes most of
that effect [4]. Demographic effects differ in direction across studies [5, 6], so they are
tested with invariance cases rather than corrected with a constant. Supervised span models still
lead skill extraction, while LLMs handle coordination and ambiguity better [7, 8]; implicit
skills are an inference and have to be labelled as such [8].

### Requirements in job offers

ESCO links skills to occupations as essential or optional, a two-level obligation at occupation
level that a posting may override [9]. Hedge and obligation cues are ambiguous out of context:
most hedge cue words also occur in non-hedging uses, and keyword baselines had low precision [10].
In contracts, models that see the surrounding structure classify obligations better [11]; in job
offers the section heading plays that role. Listed requirements are not all gates: removing
optional qualifications from real ads changed who applied [12], and degree requirements are
often inflated or replaced by "or equivalent experience" [13]. Years of experience predict
performance poorly; task-level evidence matters more [14].

### Evidence grading

Attribution is judged against an identified source [15]. Long outputs are verified fact by fact,
with partial credit [16]. Entailment-based citation checks agree with humans in most cases but
miss partial support, so they can veto a direct label but not confirm it [17]. "Not enough
information" is a separate verdict that humans also find hard (Fleiss kappa 0.68) [18].
Evidence-grading practice downgrades indirect evidence explicitly [19]. Assessment-centre
guidelines separate observing and recording from classifying and evaluating, and require
tangible evidence for each rating [20]. LLM judges blur criteria, scoring one aspect with
evidence for another [21].

### Rubrics, calibration and uncertainty

Behaviourally anchored scales derive anchors from critical incidents and keep only anchors that
independent raters assign to the same dimension [22]. Anchors moved to a different setting lost
discrimination [23], which argues for anchors per job family and level, validated on reference
cases. Checklists of yes/no items raise agreement between LLM evaluators compared with holistic
scores [24]. LLM judges show position, verbosity and self-enhancement biases [25]. Verbalised
confidence is overconfident [26]; agreement across repeated runs is a better uncertainty signal
[27]. Abstention is a designed outcome with its own threshold, not a low score [28].

### Document quality and job fit

Recruiters read résumés as biodata and rate them higher when content matches the job [29];
spelling errors cost about as much as missing experience in one recruiter experiment [30]. The
SIOP guidance on AI-based assessments separates deficiency from contamination: job-irrelevant
variance in a score lowers its validity [31]. Fit and document quality therefore need separate
outputs. About a fifth of résumés use multi-column layouts that need layout information to read
in order [32]; without that information a tool can report only what its own extraction read.

### Consistency validation

Intrinsic self-correction without external feedback does not improve reasoning reliably [33].
Verification works better when the verifying questions are answered without the draft in view
[34]. Agreement across samples flags hallucinated content [27]. Production data validation sends
disagreements to people instead of correcting them automatically [35]. For the CV check this means
deterministic rules in code, an optional targeted re-ask, and visible flags.

### Feedback and fabrication

Feedback improves performance on average but reduces it in over a third of cases, especially when
it shifts attention from the task to the person [36]. Useful feedback states the goal, the current
position and the next step [37]. In a multi-stage hiring pipeline 96.7% of baseline outputs
contained at least one unsupported claim; prompt guardrails reduced their density by 86% but half
the outputs still contained one [38]. Rewrites need deterministic checks on entities, numbers and
qualifiers, and missing details are requested, not filled in.

### Evaluation with reference sets

Krippendorff's alpha suits any number of raters, missing data and ordinal scales; the metric must
match the scale [39]. Criteria drift once evaluators see system output [40], so reference labels
are fixed before any output is shown. LLM annotation quality is task-dependent: in 9 of 27 tasks
precision or recall was below 0.5 [41]. Behavioural tests such as invariance cases complement
accuracy [42]. Success for the CV check is measured as fewer misreadings, unsupported judgements,
contradictions and fabrications, and fewer flips under invariance cases.

### Regulatory context

The EU AI Act lists systems that filter applications or evaluate candidates for recruitment as
high-risk [43]. A tool that candidates run on their own CV for practice is not intended for an
employer's selection, so it is likely outside that scope; reusing the component for employer
screening would change this. This reading is not legal advice.

## Fast classifiers alongside the LLM

Small fine-tuned encoders still outperform prompted large models on narrow classification [44];
few-shot contrastive training reaches usable accuracy with little data [45]. A cascade accepts the
classifier's label above a calibrated threshold and defers the rest to the LLM [46]. Comparable
sentence tasks reach F1 around 0.86 (hedge detection) to 0.92 (requirement types) [10, 47]. No
benchmark exists for obligation, directness or quantified outcomes in CVs and offers.

| Task | Fit for a classifier | Notes |
|---|---|---|
| Obligation of an offer sentence (must, preferred, unclear) | Good | Text-observable; the heading is part of the input |
| Quantified outcome in a CV line | Good | Rules first; a classifier for scope words and spelled numbers |
| Heading or section type of a CV line | Good | Includes letter-spaced and unconventional headings |
| Evidence directness of a CV span for a requirement | Pre-filter only | Pair input; may veto `direct`, never confirm fit |
| Alternatives, equivalences, thresholds | Rules and LLM | Structure, not a label |
| Fit, seniority adequacy, bands, recommendations, rewrites | Not suitable | Judgements of policy; no validity evidence for small classifiers |

**Jev (available now).** ProbeLoop already calls TypeSafe Jev for stated limits
([ADR 0020](../adr/0020-faster-turns-and-reviewed-transcripts.md)): one request per answer, one
`noul` question per sentence with fixed instructions and criteria, model `jev-1.14.0`, threshold
0.5 and a versioned wording (`interview/infrastructure/jev_limits.py`). The same mechanism can ask
zero-shot questions per offer sentence or CV line, which makes it the cheapest way to test the
first three tasks on a labelled set. Its use for the CV check has three conditions. The CV and
offer text leave the machine, so it is opt-in and stated in Settings like the limits reader. Each
wording and threshold is evaluated on the reference set before use and recorded with every
reading. It never decides fit, bands or feedback text.

**Laya (later).** The Laya pilot ([laya-limits-pilot.md](laya-limits-pilot.md)) shows what a
fine-tune costs. Stated limits, a property visible in the text, reached precision 0.91 and recall
0.98 on 2,549 labelled sentences; turn decisions, which are interviewing policy, stayed near the
majority rate. A CV task would need the same steps: about two to three thousand labelled
sentences per task across professions and both languages, blind labelling with measured
agreement, leave-one-profession-out evaluation, an int8 ONNX export (about 300 MB for the current
encoder) with digests in the model catalogue, and an ADR. Obligation, headings and quantified
outcomes resemble the stated-limit task; evidence directness is closer to the turn decisions and
is the riskiest candidate.

## Jev on the reference labels

On the evening of 2026-11-12, `evals/jev_classification.py` ran the Jev adapter
(`jev-1.14.0`, wordings `cv.obligation.v1`, `cv.quantified.v1` and `cv.heading.v1`, thresholds
0.5) against the frozen labels in `backend/evals/fixtures/synthetic/cv_check/` (version 2). Lines
are the units: 81 offer lines with one obligation and 3 with mixed obligations, and 462 CV lines,
55 of them holding a labelled quantity and 78 a heading. Raw scores stay outside git.

| Task | 40 questions per request | 8 questions per request |
|---|---|---|
| Obligation `must`, precision / recall | 0.91 / 0.82 | 1.00 / 1.00 |
| Obligation `preferred` | 0.86 / 0.86 | 0.97 / 1.00 |
| Heading at 0.5 | 0.19 / 0.76 | 0.62 / 0.94 |
| Quantified outcome at 0.5 | 0.28 / 0.66 | 0.41 / 0.80 |

With 40 questions per request, readings of later lines drifted towards the middle of the scale,
so the adapter now sends 8. Obligation then made one error in 81 lines: a trait sentence without
a cue scored exactly 0.5 for preference. The corpus states obligation with explicit cues and
headings, so this result is likely optimistic for offers written in looser prose.

The CV tasks were weak for two reasons. A physical line is the wrong unit: the CVs wrap a bullet
over two lines, so a quantity can start on one line and end on the next. And a question that
names a line only by its index lets the reading drift to a neighbouring line. Three changes
followed:
- CV text is judged as logical lines, with wrapped lines joined
  (`probeloop.context.domain.lines`);
- wordings `cv.quantified.v2` and `cv.heading.v2` quote the line's text as well as its index;
- choices are made on development CVs (`c01`, `c03`, `c05`, `c07`, `c09` and their variants) and
  measured once on the others (`c02`, `c04`, `c06`, `c08`, `c10` and the `c04` variant).

| Development CVs, precision / recall at 0.5 | v1, 8 per request | v1, 4 | v2, 8 | v2, 4 |
|---|---|---|---|---|
| Quantified outcome (30 lines) | 0.51 / 0.80 | 0.64 / 0.83 | 0.94 / 1.00 | 0.94 / 1.00 |
| Heading (47 lines) | 0.57 / 0.94 | 0.76 / 1.00 | 0.90 / 1.00 | 0.96 / 1.00 |

On the development CVs a threshold of 0.7 kept precision at 0.97 or more with full recall for
both batch sizes, so v2 with 8 questions per request and thresholds 0.7 became the default. On
the held-out CVs it gave 0.96 / 0.96 for quantified outcomes (24 lines) and 1.00 / 1.00 for
headings (31 lines, letter-spaced ones included). The two errors were "Built the first Tableau
workbook" read as a measure and "Staff Nurse, Acute Medical Ward (32 beds)" missed as scope.

The three tasks are now marked as evaluated (`EVALUATED` in the adapter). The set is small and
synthetic; obligation was measured on all offers, after the batch size had been chosen on the
same labels, and the offers state obligation with explicit cues. These results support using
Jev for the three line labels in the CV check; they do not establish its accuracy on real
documents, which the CV check's own measures will have to watch.

## Integration after the baseline

Offer analysis now extracts structured requirements and lets the user review their obligations.
Jev can be selected for obligation classification; heading and quantified-outcome classification
remain evaluation helpers. The [architecture](../architecture.md#preparation-and-interview-flow)
describes the integrated flow, and [configuration](../configuration.md) describes tool selection
and the text sent to TypeSafe. Matching, scoring, evidence selection and feedback have not been
remeasured against the frozen labels by this record.

## Limits of this record

- The probe uses scripted model outputs. The reference labels now exist, but matching, scoring
  and feedback error rates remain unmeasured until the full pipeline runs against them.
- Line references describe commit `81c13e1`.
- Several sources were read only at abstract or snippet level, as labelled. Evidence is thin for
  obligation classification of job-offer sentences, evidence grading in CVs, seniority-specific
  anchors, ATS parser accuracy and fabrication in CV rewriting (one recent preprint).

## Sources

1. Vaishampayan, S., et al. (2025). Human and LLM-Based Resume Matching: An Observational Study. Findings of NAACL 2025, 4823-4838. https://aclanthology.org/2025.findings-naacl.270 (abstract)
2. Chen, Q., & Xiao, Y. (2026). Competence-Preserving Resume Perturbations Expose Presentation Sensitivity in LLM Screening. arXiv:2609.16517, under review. https://arxiv.org/abs/2609.16517 (abstract)
3. Xu, J., Li, G., & Jiang, J. Y. (2025). AI Self-preferencing in Algorithmic Hiring: Empirical Evidence and Insights. AIES 2025; arXiv:2509.00462 v4. https://arxiv.org/abs/2509.00462 (abstract)
4. Rozado, D. (2025). Gender and Positional Biases in LLM-Based Hiring Decisions. arXiv:2505.17049. https://arxiv.org/abs/2505.17049 (abstract)
5. Armstrong, L., Liu, A., MacNeil, S., & Metaxa, D. (2024). The Silicon Ceiling: Auditing GPT's Race and Gender Biases in Hiring. arXiv:2405.04412. https://arxiv.org/abs/2405.04412 (abstract)
6. Wilson, K., & Caliskan, A. (2024). Gender, Race, and Intersectional Bias in Resume Screening via Language Model Retrieval. AIES 7(1), 1578-1590. https://arxiv.org/abs/2407.20371 (abstract)
7. Zhang, M., Jensen, K. N., Sonniks, S. D., & Plank, B. (2022). SkillSpan: Hard and Soft Skill Extraction from English Job Postings. NAACL 2022. https://arxiv.org/abs/2204.12811 (snippet)
8. Nguyen, K. C., Zhang, M., Montariol, S., & Bosselut, A. (2024). Rethinking Skill Extraction in the Job Market Domain using Large Language Models. NLP4HR 2024. https://aclanthology.org/2024.nlp4hr-1.3 (snippet)
9. European Commission. ESCOpedia: occupations pillar; essential and optional skills. https://esco.ec.europa.eu/en/escopedia/occupations-pillar (snippet)
10. Farkas, R., et al. (2010). The CoNLL-2010 Shared Task: Learning to Detect Hedges and their Scope in Natural Language Text. https://aclanthology.org/W10-3001 (snippet)
11. Chalkidis, I., Androutsopoulos, I., & Michos, A. (2018). Obligation and Prohibition Extraction Using Hierarchical RNNs. ACL 2018. https://arxiv.org/abs/1805.03871 (snippet)
12. Abraham, L., Hallermeier, J., & Stein, A. (2024). Words matter: Experimental evidence from job applications. Journal of Economic Behavior & Organization 225, 348-391. (snippet)
13. Fuller, J. B., Raman, M., et al. (2017). Dismissed by Degrees. Harvard Business School, Accenture, Grads of Life. (snippet)
14. Van Iddekinge, C. H., Arnold, J. D., Frieder, R. E., & Roth, P. L. (2019). A meta-analysis of the criterion-related validity of prehire work experience. Personnel Psychology 72(4), 571-598. (snippet)
15. Rashkin, H., et al. (2023). Measuring Attribution in Natural Language Generation Models. Computational Linguistics 49(4). https://arxiv.org/abs/2112.12870 (snippet)
16. Min, S., et al. (2023). FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation. EMNLP 2023. (snippet)
17. Gao, T., Yen, H., Yu, J., & Chen, D. (2023). Enabling Large Language Models to Generate Text with Citations. EMNLP 2023. https://arxiv.org/abs/2305.14627 (snippet)
18. Thorne, J., Vlachos, A., Christodoulopoulos, C., & Mittal, A. (2018). FEVER: a Large-scale Dataset for Fact Extraction and VERification. NAACL 2018. https://aclanthology.org/N18-1074 (snippet)
19. Guyatt, G. H., et al. (2011). GRADE guidelines: 8. Rating the quality of evidence: indirectness. Journal of Clinical Epidemiology 64(12), 1303-1310. (snippet)
20. Meiring, D., & Buckett, A. (2016). Best practice guidelines for the use of the assessment centre method in South Africa (5th ed.). SA Journal of Industrial Psychology 42(1). https://sajip.co.za/index.php/sajip/article/view/1298 (full text)
21. Hu, X., et al. (2024). Are LLM-based Evaluators Confusing NLG Quality Criteria? ACL 2024. https://aclanthology.org/2024.acl-long.516 (snippet)
22. Smith, P. C., & Kendall, L. M. (1963). Retranslation of expectations: An approach to the construction of unambiguous anchors for rating scales. Journal of Applied Psychology 47, 149-155. (snippet)
23. Borman, W. C., & Vallon, W. R. (1974). A view of what can happen when behavioral expectation scales are developed in one setting and used in another. Journal of Applied Psychology 59(2), 197-201. (abstract)
24. Lee, Y., et al. (2024). CheckEval: A reliable LLM-as-a-Judge framework for evaluating text generation using checklists. arXiv:2403.18771. (snippet)
25. Zheng, L., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. NeurIPS 2023 Datasets and Benchmarks. https://arxiv.org/abs/2306.05685 (abstract)
26. Xiong, M., et al. (2024). Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs. ICLR 2024. https://arxiv.org/abs/2306.13063 (snippet)
27. Manakul, P., Liusie, A., & Gales, M. (2023). SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models. EMNLP 2023. (snippet)
28. Wen, B., et al. (2025). Know Your Limits: A Survey of Abstention in Large Language Models. TACL 13, 529-556. (snippet)
29. Brown, B. K., & Campion, M. A. (1994). Biodata phenomenology: Recruiters' perceptions and use of biographical information in resume screening. Journal of Applied Psychology 79, 897-908. (snippet)
30. Lacroux, A., & Martin-Lacroux, C. (2017). Do Employers Forgive Applicants' Bad Spelling in Résumés? Business and Professional Communication Quarterly 80. https://hal-univ-tln.archives-ouvertes.fr/hal-01451842 (snippet)
31. SIOP Task Force on AI-Based Assessments (2023). Considerations and Recommendations for the Validation and Use of AI-Based Assessments for Employee Selection. https://www.siop.org/Portals/84/SIOP-AI%20Guidelines-Final-010323.pdf (full text)
32. Zhu, F., Yu, J., et al. (2025). Layout-Aware Parsing Meets Efficient LLMs: A Unified, Scalable Framework for Resume Information Extraction and Evaluation. arXiv:2510.09722. (snippet)
33. Huang, J., et al. (2024). Large Language Models Cannot Self-Correct Reasoning Yet. ICLR 2024. https://arxiv.org/abs/2310.01798 (snippet)
34. Dhuliawala, S., et al. (2024). Chain-of-Verification Reduces Hallucination in Large Language Models. Findings of ACL 2024. https://arxiv.org/abs/2309.11495 (snippet)
35. Breck, E., Polyzotis, N., Roy, S., Whang, S. E., & Zinkevich, M. (2019). Data Validation for Machine Learning. SysML 2019. (snippet)
36. Kluger, A. N., & DeNisi, A. (1996). The effects of feedback interventions on performance. Psychological Bulletin 119, 254-284. (snippet)
37. Hattie, J., & Timperley, H. (2007). The Power of Feedback. Review of Educational Research 77(1). (snippet)
38. Takano, H. (2026). Mitigating Fabrication in Multi-Stage LLM Pipelines for Hiring: An Empirical Evaluation of Prompt Guardrails and Human-in-the-Loop Checkpoints. arXiv:2608.26171 v2, single author, synthetic data. https://arxiv.org/abs/2608.26171 (abstract)
39. Hayes, A. F., & Krippendorff, K. (2007). Answering the Call for a Standard Reliability Measure for Coding Data. Communication Methods and Measures 1(1), 77-89. (full text)
40. Shankar, S., et al. (2024). Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences. UIST 2024. https://arxiv.org/abs/2404.12272 (snippet)
41. Pangakis, N., Wolken, S., & Fasching, N. (2023). Automated Annotation with Generative AI Requires Validation. arXiv:2306.00176. (snippet)
42. Ribeiro, M. T., Wu, T., Guestrin, C., & Singh, S. (2020). Beyond Accuracy: Behavioral Testing of NLP Models with CheckList. ACL 2020. (snippet)
43. Regulation (EU) 2024/1689 (AI Act), Annex III point 4. https://artificialintelligenceact.eu/annex/3/ (secondary transcript)
44. Bucher, M. J. J., & Martini, M. (2024). Fine-Tuned "Small" LLMs (Still) Significantly Outperform Zero-Shot Generative AI Models in Text Classification. arXiv:2406.08660. (snippet)
45. Tunstall, L., et al. (2022). Efficient Few-Shot Learning Without Prompts. arXiv:2209.11055. (snippet)
46. Chen, L., Zaharia, M., & Zou, J. (2023). FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance. arXiv:2305.05176. (snippet)
47. Hey, T., Keim, J., Koziolek, A., & Tichy, W. F. (2020). NoRBERT: Transfer Learning for Requirements Classification. RE 2020. (snippet)
