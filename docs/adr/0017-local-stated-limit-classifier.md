# 0017 — Local classifier for stated limits in adaptive turns

- Status: Proposed
- Date: 2026-11-10

## Context

A two-step adaptive turn ([ADR 0016](0016-adaptive-role-based-interviews.md)) first reads the
statements in the latest answer where the candidate says they do not remember something or lack
the experience. The question step then avoids asking for them again. Today an LLM call does this
reading before the decision.

In the cloud every call pays about three seconds before its first output. The limits reading
takes a median 3.5 s even when it finds nothing, out of 12.7 s for the whole move. Locally it
takes 0.8 s. Voice interviews with the cloud profile waited 17–19 s for the interviewer's voice
([measurements](../research/voice-interviews-cloud-2026-11-10.md)).

A pilot fine-tuned Laya multilingual (Apache-2.0, mmBERT-base, 322M parameters) on 2,549
synthetic answer sentences, each paired with the interviewer's question
([pilot](../research/laya-limits-pilot.md)).
- **Precision.** With one profession held out at a time, it found 288 of 294 answers with a
  stated limit (98.0%) and flagged 8 of 312 answers without one (2.6%). The LLM reading found
  69 of 70 in an earlier audit.
- **Runtime.** As int8 ONNX the model is 308 MB, takes the same decisions as fp32 and scores an
  answer in about 125 ms on CPU in Docker.

The same pilot found that the move decision itself (stay or move, purpose, actual experience) is
interviewing policy that a classifier does not reproduce. That decision stays with the
interviewer model.

## Decision

Proposed: the limits reading becomes a port with two implementations, the current LLM reading
and a local ONNX classifier. The classifier is used when its model is installed, and the LLM
reading otherwise, so behaviour without the model is unchanged.

- **Port.** The application asks for the stated limits of the latest answer given the question.
  The classifier returns whole sentences as quotes; the question rules and the prompt reserve
  already take quotes of any length.
- **Runtime.** `onnxruntime` and `tokenizers` join the backend image. They are small and do not
  pull in PyTorch. The model loads in the background when the backend starts. Until it is
  loaded, or if it fails, the LLM reading is used.
- **Model distribution.** The model is not committed and not built into the image ([ADR
  0007](0007-licensing-policy.md)). The synthetic labelled sentences are committed under
  `fixtures/synthetic/`. A `setup` profile service produces the int8 model in the `models`
  volume, in one of two ways that the owner chooses between:
  1. **Training at setup.** It downloads the Laya weights and fine-tunes them on the committed
     sentences. This is fully reproducible but takes an estimated 35 minutes on CPU.
  2. **Download.** It downloads a published model built the same way. Setup takes minutes but
     needs a hosting place and a release process.
- **Threshold.** 0.5 by default, recorded with the model.

## Consequences

- About 3.5 s less per cloud turn and about 0.7 s less per local turn, with precision measured
  at the level of the LLM reading on development data.
- One more model to version: its labels, training script, threshold and ONNX export. A change to
  the labels or the base model means retraining and measuring again.
- The labels are synthetic, come from one labeller and cover development professions only. Use
  in releases needs a check on the independent cards and on real voice transcripts, where
  recognition errors change the wording.
- The backend image gains a few tens of MB of runtime libraries; the `models` volume gains
  308 MB.
- The first load from a cold volume took 137 s in the pilot, so the LLM fallback during startup
  is needed.

## Alternatives considered

- **Reading the limits concurrently with the decision.** It saves the same time without a new
  model, but the decision no longer sees the limits.
- **Laya for the move decision.** It was measured and not adopted: it stayed at or below simple
  state features, and below the agreement between two labellers.
- **PyTorch in the backend.** It was about 2.5 times slower than ONNX on CPU in the pilot and
  adds more than a gigabyte to the image.
- **A smaller encoder.** Not measured. It would need its own labelled evaluation; Laya was chosen
  because its multilingual encoder is already licensed for this use.
