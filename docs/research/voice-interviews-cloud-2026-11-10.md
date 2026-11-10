# Voice interviews with the cloud profile (2026-11-10)

Three complete voice interviews ran on the real stack with the cloud execution profile
(`chatgpt:gpt-6.1-terra`) and two-step adaptive turns. They used professions not seen before in
development: hydraulic engineering, electrical design and food-plant maintenance. All material
is synthetic. These are development observations, not acceptance evidence: the cards, the
answers and the audit come from the same author.

## Method

**Documents.** Each case had a CV, a job offer and one resource, in different formats.

| Case | Interview | CV | Offer | Resource |
|---|---|---|---|---|
| A: senior hydraulic engineer, water network planning | technical, hard, 12 min | Markdown file | pasted text | DOCX technical report of the candidate's pilot project |
| B: junior electrical designer, apprenticeship | getting-to-know (`hr`), easy, 10 min | pasted text | HTML file | Markdown onboarding guide of the studio |
| C: line maintenance manager, frozen-food plant | behavioural, medium, 12 min | DOCX file | Markdown file | DOCX maintenance KPI report of the candidate's current plant |

**Preparation.** The documents went through the API (`/api/documents`, `/api/preparations`) with
the cloud profile. The review was done as a user would do it: the facts stating that a document
is synthetic were excluded, one fact was corrected, and each proposed role was confirmed. Case C
needed a corrected target role.

**Interviews.** `evals/voice_candidate.py` played the candidate with Piper (male
`it_IT-riccardo-x_low` for A and C, female `it_IT-paola-medium` for B). Each answer was written
only after the question arrived, never prepared in advance. Every answer was tagged with the
trait it carried, in `ground-truth.jsonl`. The planted traits were:

- strong first-hand answers;
- vague ownership;
- generic answers;
- admitted gaps;
- a wrong technical claim that contradicts the candidate's own resource (A);
- an inflated result that contradicts the uploaded KPI report (C);
- candidate questions that the documents do and do not answer.

After each call the transcript was refined automatically and a cloud report was generated.

Raw runs are under the ignored `var/voice-candidate/run-20261110-*` and
`var/test-run/voice-cloud-v1/`: documents, preparations, review log, sessions, reports, ground
truth and `voice-analysis.json`.

## Measurements

| | A | B | C |
|---|---|---|---|
| Document analysis (three in parallel) | about 6.5 min | about 6.5 min | about 6.5 min |
| Facts (candidate / job) | 49 / 17 | 19 / 30 | 21 / 31 |
| Answers | 7 | 11 | 10 |
| Fallback moves | 0 | 1 | 0 |
| WER live / refined (against the text sent to Piper) | 14.5% / 7.3% | 7.8% / 6.1% | 12.1% / 10.0% |
| Reply latency, end of answer to first interviewer audio, median / max | 17.2 s / 57.4 s | 19.3 s / 33.1 s | 17.5 s / 24.3 s |
| Interviewer question length, median / max words | 54 / 65 | 22 / 36 | 32 / 49 |
| Transcript refinement | 271 s | 371 s | 321 s |
| Report job | 149 s | 104 s | 138 s |
| Overall score | 75 | 96 | 86 |

## Interviewer behaviour

- Every vague or generic answer except one was followed by a probe for a concrete example or for
  the candidate's own actions. The exception was the vague team answer in C.
- In C the interviewer compared the inflated availability figure with the uploaded report and
  asked which period the figure referred to. The candidate then corrected it.
- In A the wrong claim on the pressure–leakage relation was not challenged during the
  interview; the report caught it.
- Questions the documents answer were answered from the documents, for example "the MT/BT course
  is internal". Questions they do not answer were declined explicitly, without invented
  details (A, B, C).
- No question asked again for a stated limit.
- Technical questions were long and often had three parts (median 54 words in A).

## Reports against the planted traits

| Planted trait | Report |
|---|---|
| A: leakage always follows the square root of pressure | Reported with the right correction, quoting the pilot's measured exponent of about 1.1 from the uploaded resource |
| A: vague ownership of the valve settings, then a first-hand follow-up | Ownership not assessed for that question: the decision did not record it as elicited, although both questions asked what the candidate did "personalmente" |
| B: generic expectations of the apprenticeship | Listed under what to improve; motivation still 100 |
| C: inflated line-2 availability, corrected after the challenge | Credited as a correction; no score reflects the first claim |
| C: vague handover answer | Listed under what to improve; ownership 75 for that question |
| A, C: admitted gaps (transients, ammonia plants) | Matrix of C marks refrigeration plants as not shown; the gap in A came only in the closing questions, which are not scored |

## Problems found

1. **Reply latency.** With the cloud profile the interviewer's voice started a median of 17–19 s
   after the end of each answer. The voice runs of 2026-11-08, before adaptive turns, had a p50
   of about 4 s. This is the main obstacle to a natural spoken interview with two-step turns
   on the cloud.
2. **A long first answer partly lost live.** The first answer of A lasted 50 s. Live
   recognition kept only its second half and reported `stt_failed`. The next question was
   built on the partial transcript. Refinement recovered the whole answer after the call, but
   it misheard "milleduecentocinquanta" as "1259".
3. **A candidate question with a stated limit led to a fallback (B).** The answer said "non ho
   mai visto come si progetta una cabina vera" and then asked whether the MT/BT course was
   internal. The decision chose a clarification to answer it. Two-step validation rejects a
   clarification on the same objective after a stated limit, so both decisions were rejected and
   the fixed fallback phrase was spoken. The question was answered only when repeated.
4. **Hypothetical probes under behavioural objectives elicit nothing.** In B and C, hypothetical
   questions under behavioural objectives were recorded with no elicited criteria, so their
   answers were not assessed. Examples are "an error found after delivery" and "a suspected
   ammonia leak". Those objectives list behavioural criteria, which are not allowed for a
   hypothetical question. Autonomy is dropped without a reasoning criterion, and nothing
   remains.
5. **A resource about the candidate's own plant was attributed to the job (C).** All facts of
   the KPI report about the candidate's current employer were stored as job facts. The
   interviewer still used them correctly as "the available documentation". In A, a comparable
   resource was attributed to the candidate.
6. **An explicit job title was missed (C).** The proposed role said the offer did not state a
   title. The offer heading read "Responsabile manutenzione di linea".
7. **Report presentation.**
   - Unassessed criteria are shown as "Non valutabile / 100".
   - Some criteria list the same or overlapping quotation twice.
   - "Contributo personale" appears twice in C's summary and criteria, once per rubric family.
   - "Domande per esercitarti" was empty in all three reports.
   - Quotations keep recognition errors of the refined transcript, for example "lotenze" and
     "pegime".
8. **Requirement matrix.** A marks pressure transients as demonstrated in the documents. The CV
   says they were done with a specialist's support.

## Not observed

There were no invented personal references, no lost answers after refinement and no unverified
quotations. No provider feature was rejected.
