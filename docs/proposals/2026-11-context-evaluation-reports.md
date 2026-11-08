# Proposal: context acquisition, CV review, interview evaluation and reports

- Status: reviewed by the owner; decisions recorded in [section 9](#9-decisions)
- Date: 2026-11-07
- Scope: M4, M5 and M7 of the [roadmap](../roadmap.md), plus CV review.
- Implementation status (2026-11-08): M4 is complete; M5 is implemented and verified locally with
  live extraction measurements and the browser flow. CV review is implemented with a live-model
  smoke run and versioned reports. M7, M6 preferences/i18n and M9 data/history code are implemented
  as an unfinished development checkpoint. Model quality/latency, final UI verification and the
  two voice acceptance runs remain open. See the [continuation notes](../handoffs/2026-11-08-assessment-continuation.md).
  The decisions below govern their implementation.

## 1. Starting point and proposed order

After M3 a voice interview runs end to end. Each session keeps:

- the transcript (`transcript.json`, `transcript.md`);
- the audio of every turn and of the whole conversation;
- the latency of every reply (`metrics.jsonl`).

The synthetic voice candidate (`evals/voice_candidate.py`) can run whole interviews without a
person. Interviewer context is still a fixed sample brief, and nothing evaluates the candidate.

**Proposed order:** M4, then M5, then the CV review (new), then M7, M6 and M9. M8 (web and
GitHub enrichment) is dropped: nothing is fetched from the internet (section 2.5). The roadmap puts
the final UI (M6) before evaluation (M7). Reports are the point of the product, and the report
pages are most of what M6 would polish, so evaluation should come first.

## 2. Acquiring the context (M5)

### 2.1 Inputs

| Input | Form | How it is read |
|---|---|---|
| CV | PDF (LinkedIn: its PDF export) | Text extraction with page and offset |
| Job offer | PDF or pasted text | Same extraction as the CV |
| Job offer described in words | Free text ("junior PHP web developer, web agency, 0–2 years…") | The model drafts a job offer that the user edits (section 2.2) |
| Resources | Each with a title chosen by the user, and either text typed in a box or a text file (txt, md, json, xml, html, docx, pdf) | Same pipeline as the CV; kept in reusable profiles (section 2.5) |

Nothing is fetched from the internet: links in the documents are not followed.

### 2.2 Without a real job offer

The job offer is optional. Without one the user picks one of two paths:

- **A. Getting-to-know interview.** The model infers the professional area and the seniority from
  the CV, each with the CV facts that support it, and the user confirms or corrects them. The
  interview is then an HR and behavioural conversation for a generic company in that area. There
  is no requirement matching, and the report says so.
- **B. Job offer from a description.** The user describes the role in a text box. The model drafts
  a plausible job offer: title, kind of company, responsibilities, required and preferred
  requirements, seniority and years of experience. The draft opens in an editor before the
  interview. It is stored as a job offer with origin *generated*, and the review screens and the
  report label it "drafted from your description", so it is never presented as a real posting.
  From there it goes through the same requirement extraction as a real offer.

### 2.3 Pipeline

Each step is a job with progress, and each output is stored and reused by content hash.

1. **Store** the blob (sha256) and **extract** the text in a process pool, with a timeout and a
   page limit. Flag invisible text (white on white, tiny fonts).
2. **Extract facts** section by section with a constrained-JSON LLM call. Each fact carries:
   - a statement;
   - a kind: skill, role, project, achievement, education or requirement;
   - a verbatim source quote.
3. **Verify the quotes** in code (fuzzy match against the page text):
   - a fact without a verified quote is downgraded to *inferred*, or dropped;
   - verification sets the fact's origin: *declared* (the CV says it), *observed* (an external
     source shows it) or *inferred*.
4. **Match requirements.** Each job requirement is matched to the facts that support it: met,
   partly met, not shown. Every match cites its facts.
5. **Review.** The user confirms, corrects, excludes or adds facts, and sees the status of every
   external resource (section 2.5). Approval freezes an immutable `ContextSnapshot`.

### 2.4 What the snapshot feeds

- **The interviewer brief and a topic plan.** The `Planner` probes the requirements that are not
  shown and the vague claims.
- **A vocabulary of technical terms** (product, library and company names). It goes to:
  - Whisper's `initial_prompt` in the refinement pass (the M3 run showed what it fixes);
  - the interviewer prompt, so a garbled term is read as the likely word instead of prompting a
    clarification request;
  - optionally, a conservative fuzzy correction of the live transcript.
- **The CV review and the evaluator** (section 4.1 lists what the evaluator receives).

### 2.5 Resources and profiles

Anything beyond the CV and the job offer (project notes, a portfolio, a README, a cover letter)
is added by the user as a **resource**: a title of their choice, plus either text typed in a box
or one text file (txt, md, json, xml, html, docx or pdf). The resource screen shows one empty
title-and-content row; as soon as it is filled, a new empty row appears below it, so the user
adds as many as they need.

Resources are kept in **profiles**, so the same set can be reused across interviews:

1. Before the resources, the user picks an existing profile or creates a new one.
2. The resource screen shows the profile's resources, which can still be changed.
3. If they were changed, the user chooses: overwrite the profile, save them as a new profile, or
   use them for this interview only without saving.

HTML and XML are reduced to their text; tags, scripts and styles are dropped. Each resource is
data, delimited in prompts like the CV.

### 2.6 Safety

- Documents and resources are data. They are delimited in prompts, and extraction calls have no
  tools.
- Quotes are verified, and invisible text is flagged before review.
- No service fetches anything from the internet.

## 3. CV review (new)

A review of the CV, before or without an interview. It runs against a real job offer, against a
generated one (section 2.2, path B), or against the area inferred from the CV (path A).

The owner's general CV rating guidelines were incorporated on 2026-11-08 in
[CV rating requirements](2026-11-cv-rating-guidelines.md). That document defines contextual
checks, non-penalty rules, evidence limits, draft anchors and synthetic calibration cases.

**Rubric v1** (versioned YAML, like the interview rubrics):

| Criterion | How it is judged |
|---|---|
| Relevance to the target | Against the requirement matrix with a job offer; against the confirmed area without one |
| Evidence of impact | Concrete qualitative or quantitative outcomes with verified quotes; number counts are diagnostic, not the grade |
| Specificity and ownership | Concrete actions and individual contribution, including relevant unpaid work and projects |
| Clarity and structure | Recognisable organisation, relevant detail and readability; visual checks require layout evidence |
| Consistency | Dates and internal coherence; gaps and overlaps are contextual review flags, not automatic deductions |
| Depth for the target level | Detail appropriate to the confirmed target, judged from cited evidence in the document |
| Machine readability | Observed extraction quality and limitations, without a universal ATS compatibility claim |

**Output:**
- a score per criterion (1–5, or *not assessable*), each with verified quotes;
- strengths, and gaps against the target;
- rewrite suggestions that quote the original line;
- the questions an interviewer is likely to ask. These also feed the interview plan.

The output language follows the application setting (section 7).

**Rules:**
- Deterministic checks wherever possible; the LLM only where judgement is needed.
- No statement about the candidate without a quote from the CV.
- Scores are formative, not predictions.
- No universal deductions for page count, template, photo, column count, missing introduction or
  lack of numerical metrics. Apply explicit employer instructions and observed defects in context.
- Do not infer visual properties from plain text or equate a quoted claim with verified ability.
- Links are not fetched; reachability is not assessed.

**Evaluation:** synthetic CVs with planted problems (unquantified results, a date gap, a
requirement not shown), measuring how many of them the review detects.

## 4. Interview evaluation and the final report (M7)

### 4.1 After the call

1. **Refinement.** A job re-transcribes the stored answers with Whisper turbo and the vocabulary.
   Section 4.5 explains when it runs.
2. **Review.** The transcript editor (M4) highlights low-confidence words. Every correction makes
   a new revision.
3. **Evaluation**, in the background, on a chosen transcript revision:
   1. *Segment* the interview into answer units: a question, the answer and its follow-ups, the
      topic, and the kind of question (past behaviour, hypothetical, technical, motivation).
   2. *Judge* each unit against the criteria of its kind (section 5): constrained JSON, scores
      with quotes, and *not assessable* when the evidence is thin.
   3. *Verify* every quote against the transcript in code; unverified judgements are dropped.
   4. *Aggregate* in code: per-criterion scores and an overall score, each with the number of
      answers it rests on.
   5. *Render* the report, and keep it versioned: regenerating after corrections makes v2 and
      keeps v1.

**What the evaluator receives.** Accuracy matters more than speed, so each judge call gets the
whole context it needs:

- the answer unit (ADR 0012: only its own turns, since neighbouring answers leaked into judgements);
- the rubric of the unit's kind, with its anchors;
- the user's documents as approved in the snapshot: the CV, the job offer (real or generated) and
  the resources, as delimited data;
- the snapshot's facts and the requirement matrix.

A judge call is about 5k tokens (rubric 1k, documents 3k, unit 1k), within an 8k context.

**Model and timing.** The evaluator is a separate model profile: `qwen3.5:9b`, with thinking off
for judging since [ADR 0012](../adr/0012-interview-evaluation-pipeline.md).
It runs only after the call, because any other model call during the interview would evict the
interviewer's prompt cache, and it runs asynchronously: the user can leave the page and gets a
notification when the report is ready. The run time on machine A is measured in M7 and shown as
an estimate before the run.

### 4.2 The overall rating

The overall score is the weighted mean of the criterion scores (equal weights in v1, section 5).
It is computed only when enough criteria are assessable; otherwise the report says there is not
enough evidence. The report shows it:

- as a band (for example "solid", "needs work") as well as a number;
- with the evidence count;
- with the statement that it is a practice measure, not a hiring prediction.

### 4.3 Report contents

- A summary of the interview.
- **Scores per criterion**, each with its justification and quotes. The quotes link to the
  transcript turns and to their audio.
- **Strengths**, and **areas to improve**, each with what a stronger answer would have contained.
- **Technical errors**, each with the quote and the correct statement.
- **Delivery**, computed from the audio and the timings without an LLM:
  - speaking rate;
  - filler words;
  - long pauses inside answers (from the voice activity detector);
  - time between the question and the start of the answer;
  - answer length against the time budget;
  - the share of time each side spoke.
- **Coverage** of topics and job requirements.
- **What to practise next**, and the trend against earlier sessions with the same rubric version
  (M9).

### 4.4 Exports

- Markdown and JSON, as the transcript already has.
- **PDF**, rendered from an HTML template of the report with WeasyPrint (BSD-3-Clause; it loads
  Pango, LGPL, as a system library, which ADR 0007 allows). WeasyPrint runs no JavaScript, and its
  URL fetcher is replaced by one that refuses every request, so transcript text cannot pull in
  remote content.
- The audio of the whole interview.

### 4.5 When the refinement runs

**Decision: after the call, not during it.** The refinement runs once the call has ended, in
the same `stt-worker` that serves the live engine, when nothing latency-sensitive is running. The
measurement behind the decision:

**Set-up (2026-11-07, machine A).** Ryzen 9 3900X (24 threads), 16 GB of RAM, of which the
Docker VM gets 7.7 GB, and an RTX 2070 Super with 8 GB. A second worker ran Whisper turbo int8
with 4 CPUs and 4 threads, re-transcribing the 16 answers of the synthetic interview in a loop.
At the same time the critical path of a reply was measured 12 times:

- Parakeet on a 6-second final segment;
- Piper on a first clause (38 characters) and on a full sentence (164 characters);
- Ollama's time to the first token and to 60 tokens.

These ran idle before the load, under load, and idle again after.

**Results.**

| Step (median) | Idle (after) | With Whisper busy |
|---|---|---|
| Parakeet, 6 s segment | 0.42 s | 0.53 s |
| Piper, first clause | 0.15 s | 0.25 s |
| Piper, full sentence | 0.30 s | 0.87 s |
| LLM, first token | 0.21 s | 0.33 s |
| LLM, 60 tokens | 2.27 s | 2.73 s |

| Resource | Measured |
|---|---|
| Whisper speed, idle, 4 CPUs | 0.58× real time on 20–22 s answers. A 9.7 s answer also took 10 s: Whisper always processes 30 s windows, so a short answer costs a full window |
| Whisper speed, while the live path runs | 0.80× real time |
| Whisper memory | about 0.9 GB once loaded, 1.3 GB at the peak while loading |
| Whisper loading in a fresh worker | 217 s, on one core |
| Free host memory | 2.2 GB before the test; 0.7 GB at the lowest, while Whisper loaded |

**Reading.**

- **CPU is not the problem.** Under load the first audio of a reply comes about 0.3–0.5 s later:
  - 0.1 s more to the first token;
  - token generation about 17% slower;
  - 0.1 s more to synthesise the first clause.

  Parakeet's change is within the noise of the idle runs. Later sentences take about three times
  as long to synthesise, but they are still produced much faster than they play. The language
  model is sensitive to CPU load because on this machine 16% of `ministral-3:8b` runs on the CPU
  (the desktop applications hold part of the video memory).
- **Memory is the problem.** Whisper adds about 1 GB to a host left with about 2 GB free, and the
  load took the host down to 0.7 GB. Right after the load, with Whisper idle, Piper and Parakeet
  stalled for 3–30 s in three of the twelve rounds. They did not stall later. Paging after the
  load is the likely cause; it was not proven.
- **Little gain during the call.** Using the refined text in the interviewer's context would
  rewrite earlier messages and invalidate its prompt cache. The main gain would be a report a few
  minutes earlier, and the report is asynchronous anyway.

**After the call.** On the same machine, with the worker's 6 threads and nothing else running, a
10-minute interview with about 16 answers of 20 s each should take about 2–3 minutes: one
30-second window per answer, 11 s each measured with 4 threads, less with 6. Two optimisations
to measure in M4:

- Join short answers into shared 30-second windows and split the result by word timestamps.
- Load Whisper while the call ends, so the 3.6-minute load (the cold load measured above; to be
  measured again without memory pressure) overlaps the transcript review.

**To revisit** on a machine with more memory, or if a smaller refinement model (Whisper small or
medium) gives most of the vocabulary gain at a fraction of the memory.

## 5. Rubrics v1

### 5.1 What the research says

- **Structure raises reliability and validity.** The review by Levashina, Hartwell, Morgeson and
  Campion (2014) groups the components of a structured interview into content (questions based on
  the job, the same questions for every candidate, better question types) and evaluation (rating
  each answer, anchored rating scales, trained raters). It reports that anchored rating scales
  improve reliability and validity, partly by controlling biases and by making the same
  job-related information salient to every rater. It also reports that hypothetical
  ("situational") questions have slightly lower criterion validity than questions about past
  behaviour.
- **Practical guidance** from the US Office of Personnel Management: 4–6 competencies per
  interview, one proficiency range for all of them (3 to 7 levels, at least three of them
  described), equal weights unless a different weighting is justified in writing, and example
  answers for each level. It warns about central tendency (rating everything in the middle).
- **STAR structures the answer; it is not the score.** Scorecards for behavioural interviews
  score the evidence an answer reveals: the candidate's own part, specific actions, results
  (quantified where possible), and depth when the interviewer probes. A hypothetical question
  produces a plan with no result, so it is scored differently.
- **Technical rubrics** from engineering organisations converge on the same dimensions:
  understanding of the problem and clarifying questions, approach, correctness, trade-offs, and
  communication of the reasoning.
- **Screening rubrics** score motivation, relevant experience and communication, and keep
  logistics (salary expectations, notice period, location) out of the score.
- **LLMs as judges.** Rubric scoring with an LLM shows position bias: the model prefers score
  options at particular positions of the list, and averaging over permutations of the list
  improves agreement with human judges. Evidence-anchored protocols require citations that can be
  checked mechanically. LLM ratings of personality from interview answers were found unreliable
  and potentially biased, so ProbeLoop scores observable answer quality only, never personality or
  "culture fit".

Most practitioner material is vendor templates; the design rests on the review and on the OPM
guidance, and uses the templates only for criterion names and examples.

### 5.2 Design rules

- **One scale:** 1–5 with anchors written for levels 1, 3 and 5, plus *not assessable*. Levels 2
  and 4 mean "between the two anchors".
- **4–6 criteria per kind of question**, equal weights in v1. A rubric that changes a weight
  states why in the YAML.
- **Each answer unit is scored on its own** before aggregation, as structured interviews do.
- **Hypothetical answers** are marked as such. They can score on reasoning, but not on results.
- **Logistics are recorded, not scored.**
- **Against the judge's biases:** each unit is judged twice, with the anchors listed in ascending
  and in descending order, and the two scores are averaged; a disagreement of two points or more
  marks the score as unstable in the report. Every score needs quotes verified by code.
- **Calibration** uses the synthetic personas (section 6): the anchors are revised until the
  thresholds hold, and the score distribution is checked for central tendency.

### 5.3 Criteria

Each interview type uses the criteria that match its questions. A mixed interview scores each unit
with the criteria of its kind, so its report has a technical and a behavioural part.

**Screening (HR)**, and the getting-to-know interview of section 2.2:

| Criterion | Level 1 | Level 3 | Level 5 |
|---|---|---|---|
| Motivation for the role | Generic reasons, or only pay and title | Some reasons specific to the role, partly vague | Specific reasons tied to the role, the company and the candidate's path |
| Relevant experience | Cannot connect the experience to the role | Connects it in general terms | Connects specific experiences to the role's main requirements, with examples |
| Career narrative | Moves and gaps unexplained or contradictory | Plausible but thin explanations | A coherent account of choices, moves and gaps |
| Communication | Off the question, disorganised | Answers the question with some digressions | Direct, organised, at the right length |

Logistics recorded without a score: salary expectations, notice period, location, availability.

**Behavioural** (questions about past behaviour):

| Criterion | Level 1 | Level 3 | Level 5 |
|---|---|---|---|
| Ownership | Only what the team did; cannot say their own part | Own actions mixed with the team's | Own decisions and actions, why they were taken, and what others did |
| Specificity | A generic or hypothetical account | One real situation, few concrete details | A real situation with concrete context, constraints and actions |
| Results | No outcome | An outcome stated in general terms | A measurable outcome, including what did not work |
| Reflection | No lesson, or a stock phrase | A lesson stated without applying it | A concrete lesson, and how it changed later work |
| Depth under follow-up | Contradicts or repeats when probed | Adds some detail when probed | Stays consistent and adds detail two levels down |

**Technical:**

| Criterion | Level 1 | Level 3 | Level 5 |
|---|---|---|---|
| Accuracy | Wrong statements on core points | Mostly correct, with imprecisions | Correct and precise; corrects themself when unsure |
| Depth | Names tools and terms only | Explains how something works | Explains why, internals and limits, beyond the surface |
| Problem solving | Jumps to a solution without understanding the problem | Clarifies some points, a workable approach | Clarifies the problem, breaks it down, compares alternatives |
| Trade-offs | Presents one option as always right | Mentions alternatives | Weighs costs and benefits, and says when they would choose otherwise |
| Practical experience | No first-hand example | Examples without detail | First-hand examples with concrete choices and outcomes |
| Communication of reasoning | Hard to follow | Understandable with gaps | Structured, precise, adapted to the listener |

Technical errors are reported separately (section 4.3), whatever the score.

### 5.4 Sources

- Levashina, Hartwell, Morgeson, Campion (2014), "The structured employment interview: narrative
  and quantitative review of the research literature", *Personnel Psychology* 67(1).
  <https://works.bepress.com/christopher-hartwell/4/>
- US OPM, *Structured Interviews: A Practical Guide*.
  <https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews.pdf>
- US OPM, "How do I score a structured interview?"
  <https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/structured-interviews/how-do-i-score-a-structured-interview-how-do-i-assign-points-to-the-content-areas-and-rating-scale/>
- AIHR, "Behaviorally Anchored Rating Scale: Examples + Guide".
  <https://www.aihr.com/blog/behaviorally-anchored-rating-scale/>
- Tech Interview Handbook, "Coding interview rubrics".
  <https://www.techinterviewhandbook.org/coding-signals/>
- Carta Engineering, "Bringing structure to the engineering interview".
  <https://medium.com/building-carta/bringing-structure-to-the-engineering-interview-e0b005293a4b>
- Metaview, "Interview scorecard template".
  <https://www.metaview.ai/resources/blog/interview-scorecard-template>
- "Am I More Pointwise or Pairwise? Revealing Position Bias in Rubric-Based LLM-as-a-Judge"
  (2026). <https://arxiv.org/abs/2602.02219>
- RULERS, an evidence-anchored rubric scoring protocol (2026).
  <https://www.arxiv.org/pdf/2601.08654>
- Zhang, Koutsoumpis, Oostrom et al. (2024), "Can large language models assess personality from
  asynchronous video interviews?", *IEEE Transactions on Affective Computing*.
  <https://research.tilburguniversity.edu/en/publications/can-large-language-models-assess-personality-from-asynchronous-vi/>

## 6. Measuring the evaluator with synthetic candidates

The voice candidate gets a second answer source: an LLM persona that answers from a persona card
with planted traits:

- a wrong technical claim at a given turn;
- vague ownership;
- an admitted gap;
- an excellent answer to one question.

This gives interviews whose ground truth is known. Text-mode runs are fast; voice runs add real
recognition errors. Proposed thresholds:

| Measure | Threshold |
|---|---|
| Planted problems detected | ≥ 80% |
| Personas ranked in the right order (strong above weak) | ≥ 90% of pairs |
| Quotes in reports not verified by code | 0 |
| Overall score spread over five regenerations | ≤ 0.5 points on a 5-point scale |

## 7. Application settings

A settings page (M6, brought forward where an earlier milestone needs it) holds:

- **Language** of the interface, and the default for new interviews, CV reviews and reports. Each
  interview can still override it.
- **Audio volume** of the interviewer.
- **Theme**: light, dark, or the system's.

The language setting is needed by the CV review and the reports, so it arrives with the first of
them; volume and theme can wait for M6.

## 8. End of the interview, as the user sees it

1. The call ends. The full transcript and audio are already saved; this works today.
2. A processing screen shows the refinement progress.
3. "Review your transcript": editable, with low-confidence words highlighted.
4. "Generate report" starts the evaluation in the background. The user can leave; a notification
   says when the report is ready.
5. The report page: scores, evidence linked to the transcript and the audio, and the downloads
   (Markdown, JSON, PDF, audio).

## 9. Decisions

Recorded on 2026-11-07 from the owner's answers to the first draft.

| Question | Decision |
|---|---|
| Interviews and CV reviews without a job offer | Both supported: a getting-to-know interview for the area inferred from the CV, or a job offer drafted from the user's description and edited before the interview (section 2.2) |
| Language of the output | An application setting, next to audio volume and theme (section 7) |
| Rubrics | Drafted from the literature on structured interviews (section 5), to be calibrated with synthetic personas |
| Evaluator | `qwen3.5:9b` with thinking, asynchronous, with the user's documents in context; accuracy over speed (section 4.1). Revised on 2026-11-08 by ADR 0012: judging without thinking, evidence-first schemas |
| Exports | Markdown, JSON and PDF (section 4.4) |
| Background refinement during the interview | Not now: it costs little CPU, but about 1 GB of memory that machine A does not have to spare. Refinement runs after the call (section 4.5) |
| External sources | Revised on 2026-11-07: nothing is fetched from the internet. Resources are titled text or text files added by the user, saved in reusable profiles (section 2.5). The job offer no longer accepts a URL |
