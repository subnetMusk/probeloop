# Proposal: context acquisition, CV review, interview evaluation and reports

- Status: draft for review
- Date: 2026-11-07
- Scope: M4, M5, M7 and M8 of the [roadmap](../roadmap.md), plus a CV review that the roadmap does
  not have yet. Nothing here is implemented; this is the design to discuss before those
  milestones start.

## 1. Starting point and proposed order

After M3 a voice interview runs end to end. Each session keeps:

- the transcript (`transcript.json`, `transcript.md`);
- the audio of every turn and of the whole conversation;
- the latency of every reply (`metrics.jsonl`).

The synthetic voice candidate (`evals/voice_candidate.py`) can run whole interviews without a
person. Interviewer context is still a fixed sample brief, and nothing evaluates the candidate.

**Proposed order:** M4, then M5, then the CV review (new), then M7, M6, M8 and M9. The roadmap puts
the final UI (M6) before evaluation (M7). Reports are the point of the product, and the report
pages are most of what M6 would polish, so evaluation should come first.

## 2. Acquiring the context (M5, then M8)

### 2.1 Inputs

| Input | Form | How it is read |
|---|---|---|
| CV | PDF (LinkedIn: its PDF export) | Text extraction with page and offset |
| Job offer | PDF, pasted text or URL | URL fetched once through `UrlGuard` |
| Supporting documents | PDF or text (portfolio, project notes) | Same pipeline as the CV, typed "supporting" |
| External links (M8) | GitHub, personal site, other pages | GitHub API facts; pages through `UrlGuard` and trafilatura |

### 2.2 Pipeline

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
5. **Review.** The user confirms, corrects, excludes or adds facts. Approval freezes an immutable
   `ContextSnapshot`.

### 2.3 What the snapshot feeds

- **The interviewer brief and a topic plan.** The `Planner` probes the requirements that are not
  shown and the vague claims.
- **A vocabulary of technical terms** (product, library and company names). It goes to:
  - Whisper's `initial_prompt` in the post-interview pass (the M3 run showed what it fixes);
  - the interviewer prompt, so a garbled term is read as the likely word instead of prompting a
    clarification request;
  - optionally, a conservative fuzzy correction of the live transcript.
- **The CV review and the evaluator.** The evaluator gets the snapshot, never the raw documents.

### 2.4 Safety

- External content is data. It is delimited in prompts, and extraction calls have no tools.
- Quotes are verified, and invisible text is flagged before review.
- `UrlGuard` blocks private addresses, limits redirects and pins resolved IPs. It honours robots
  and caps size and time.
- LinkedIn is not scraped: the user uploads its PDF export.

## 3. CV review (new)

A review of the CV, on its own or against a job offer, before or without an interview.

**Rubric v1** (versioned YAML, like the interview rubrics):

| Criterion | How it is judged |
|---|---|
| Relevance to the job's requirements | From the requirement matrix (only with a job offer) |
| Evidence of impact | Quantified results, cited; counting numbers and units is deterministic |
| Specificity and ownership | Concrete actions and the candidate's own part, not team claims |
| Clarity and structure | Standard sections, length, readability; mostly deterministic checks |
| Consistency | Dates, overlaps and gaps; deterministic |
| Depth for the target level | LLM judgement with cited evidence |
| Machine readability | Text extractable, no essential content in images or tables only |

**Output:**
- a score per criterion (1–5, or *not assessable*), each with verified quotes;
- strengths, and gaps against the job;
- rewrite suggestions that quote the original line;
- the questions an interviewer is likely to ask. These also feed the interview plan.

**Rules:**
- Deterministic checks wherever possible; the LLM only where judgement is needed.
- No statement about the candidate without a quote from the CV.
- Scores are formative, not predictions.

**Evaluation:** synthetic CVs with planted problems (unquantified results, a date gap, a
requirement not shown), measuring how many of them the review detects.

## 4. Interview evaluation and the final report (M7)

### 4.1 After the call

1. **Refinement.** A job re-transcribes the stored answers with Whisper turbo and the vocabulary.
   The UI shows progress; the job takes about half the audio's duration on 8 CPUs.
2. **Review.** The transcript editor (M4) highlights low-confidence words. Every correction makes
   a new revision.
3. **Evaluation**, on demand ("Generate report"), on a chosen transcript revision:
   1. *Segment* the interview into answer units: a question, the answer and its follow-ups, and
      the topic.
   2. *Judge* each unit against the rubric of the interview type: constrained JSON, scores with
      quotes, and *not assessable* when the evidence is thin.
   3. *Verify* every quote against the transcript in code; unverified judgements are dropped.
   4. *Aggregate* in code: per-criterion scores and an overall score (weighted by the rubric),
      each with the number of answers it rests on.
   5. *Render* the report, and keep it versioned: regenerating after corrections makes v2 and
      keeps v1.

The evaluator is a separate model profile (`qwen3.5:9b` is the candidate, with thinking allowed,
since latency does not matter here). It runs only after the interview, because any other call to
the model during the call would evict the interviewer's prompt cache.

### 4.2 The overall rating

The overall score is the rubric-weighted mean of the criterion scores. The report shows it:

- as a band (for example "solid", "needs work") as well as a number;
- with the evidence count;
- with the statement that it is a practice measure, not a hiring prediction.

### 4.3 Report contents

- A summary of the interview.
- **Scores per criterion**, each with its justification and quotes. The quotes link to the
  transcript turns and to their audio.
- **Strengths**, and **areas to improve**, each with what a stronger answer would have contained.
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
- **Export** as Markdown and JSON, plus the audio. PDF only if needed.

## 5. Measuring the evaluator with synthetic candidates

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

## 6. End of the interview, as the user sees it

1. The call ends. The full transcript and audio are already saved; this works today.
2. A processing screen shows the refinement progress.
3. "Review your transcript": editable, with low-confidence words highlighted.
4. "Generate report", then the report page with the scores, the evidence linked to the transcript
   and audio, and the downloads.

## 7. Questions for the owner

1. **CV review.** Should it also run without a job offer? Should the output always be in
   Italian?
2. **Rubrics.** I can draft the criteria per interview type (HR, behavioural, technical, mixed)
   for you to review. Is that the right starting point?
3. **Evaluator model.** Is `qwen3.5:9b` with thinking on acceptable, given slower reports?
4. **Exports.** Are Markdown and JSON enough, or is a PDF needed?
5. **Live transcript.** Is a refinement after the interview enough, or should each answer also
   be re-transcribed in the background during the interview? The background option needs a second
   recognition worker, so it cannot slow the live path.
6. **External links.** Which sources matter (GitHub, personal site, portfolio)? LinkedIn would
   come only through its PDF export.
