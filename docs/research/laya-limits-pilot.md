# Laya pilot: local classifiers for adaptive turn steps (2026-11-10)

The two-step adaptive turn makes up to three model calls in a row. In the cloud each call pays
about three seconds before its first output
([measurements](voice-interviews-cloud-2026-11-10.md#where-the-reply-latency-goes)). This pilot
asked which turn steps a small local classifier could take over without losing precision. The
classifier is Laya multilingual 0.4.30 (Apache-2.0; mmBERT-base encoder, 322M parameters). All
data are synthetic development conversations. Scripts, labels and results are in the ignored
`var/test-run/laya-pilot-v1/`; trained weights stay in the ignored `var/laya/`.

## Data and labels

- **Contexts.** 701 decision contexts were rebuilt from 61 stored adaptive sessions: every
  interviewer move after a candidate answer, with coverage, engagement and the time directive
  derived from the conversation. 606 remained after removing the moves where closing was the
  only legal option.
- **Labels.** Eight Claude subagents labelled the 606 contexts blind, following a written policy
  guide: stay or move, next objective, purpose, actual experience and stated-limit quotes.
- **Second labeller.** `gpt-6.1-terra`, the production decision, labelled 247 of them before it
  was stopped: half its requests failed under parallel load.
- **Agreement between the two labellers.** Stay 0.86, purpose 0.76, actual experience 0.75,
  presence of a stated limit 0.98. On the 137 contexts Claude marked high confidence, stay and
  purpose together agreed in 0.89.

Evaluation always leaves one profession out. Economics and Economia, and Medicine and Medicina,
count as one profession each; the three voice-interview professions form one group.

## Turn decisions: not adopted

| Accuracy against Claude labels | Majority | Frozen Laya + linear head | TF-IDF | State features |
|---|---|---|---|---|
| Stay on the objective | 0.62 | 0.60 | 0.69 | 0.79 |
| Purpose when staying | 0.60 | 0.61 | 0.59 | 0.69 |
| Actual experience | 0.54 | 0.56 | 0.58 | 0.61 |

Fine-tuning the whole encoder did not help the actual-experience decision. With Software
engineering held out it reached 0.59, against 0.59 for the state features. With Medicine held
out it reached 0.53, the majority rate; its training loss fell to 0.095, so it memorised rather
than generalised. These decisions are interviewing policy rather than facts in the text: two
labellers already disagree on a quarter of them, and the local and cloud interviewers agree on
only 0.45–0.69. A classifier would imitate one labeller's style. If the interviewer model should
stop making them, a code policy is the better route, judged on full interviews.

## Stated limits: adopted as a candidate

A sentence of the answer is positive when it overlaps a quoted statement that the candidate does
not remember something or lacks the experience. The input pairs the sentence with the
interviewer's question, so that limits of data or method can be told apart from the candidate's
own limits. There are 2,549 sentences, 362 of them positive.

| Answers containing a stated limit | Found | Answers without one flagged |
|---|---|---|
| Frozen Laya + linear head | 272/294 (92.5%) | 14/312 (4.5%) |
| Fine-tuned Laya, threshold 0.5 | 288/294 (98.0%) | 8/312 (2.6%) |
| Fine-tuned Laya, threshold 0.7 | 286/294 (97.3%) | 6/312 (1.9%) |
| Production LLM reading, earlier audit | 69/70 (98.6%) | 3 extra quotes in 80 answers |

At threshold 0.5 sentence precision is 0.91 and recall 0.98. The LLM row comes from a different
audit of the recorded two-step answers, so the comparison is indicative.

**Runtime.** The fine-tuned model was trained on every sentence, about two minutes on an RTX 2070
SUPER, and exported to ONNX. Dynamic int8 quantisation reduces it from 1.2 GB to 308 MB and
takes the same decision as fp32 on all 2,549 sentences. A container with only `onnxruntime` and
`tokenizers` scores one answer, every sentence with the question, in a median of 125 ms (p90
161 ms). Loading took 4 s with a warm volume and 137 s on the very first read.

## Limits of the pilot

- The labels come from one labeller, are synthetic and cover development professions only. The
  independent cards were not used.
- The voice-interview professions contribute only 21 contexts.
- The classifier returns whole sentences, while the LLM quotes a substring.
