# 0017 — Local classifier for stated limits in adaptive turns

- Status: Accepted
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

The limits reading is a port with the current LLM reader and a local ONNX classifier. The user
selects its tool in Settings, independently of the interviewer, analysis and evaluation tools
([ADR 0018](0018-per-role-processing-tools.md)). Without an installed classifier the LLM options
remain available. No reader is substituted automatically during an interview.

- **Port.** The application asks for the stated limits of the latest answer given the question.
  The classifier returns whole sentences as quotes; the question rules and the prompt reserve
  already take quotes of any length.
- **Runtime.** `onnxruntime` and `tokenizers` join the backend image. They are small and do not
  pull in PyTorch. The model loads in the background when the backend starts. Its option is
  disabled until checksum verification, loading and a small inference check succeed. If the
  selected reader fails during the interview, the interview pauses and retains its answers.
- **Model distribution.** The model is not committed and not built into the image ([ADR
  0007](0007-licensing-policy.md)). The synthetic labelled sentences are committed under
  `fixtures/synthetic/`. ADR 0019 adds browser installation through the internal provisioner.
  The provisional checkpoint is public at
  [submsk/probeloop-laya-stated-limits](https://huggingface.co/submsk/probeloop-laya-stated-limits),
  pinned to commit `4d8892cf85d84772b072b44e6db4515a6a6093f7`. The app downloads only the
  int8 ONNX and tokenizer and verifies their approved SHA-256 digests. The legacy `limits-model`
  setup command can still install a preserved local export. Training is not part of startup
  or setup; the full Safetensors weights are a separate maintainer artifact.
- **Threshold.** 0.5 by default, recorded with the model.
- **CPU budget.** Two inference threads by default, configurable with
  `PROBELOOP_LIMITS_THREADS`. Worker spinning is disabled so the reader does not compete with
  speech services between calls ([ONNX Runtime thread management](https://onnxruntime.ai/docs/performance/tune-performance/threading.html)).

## Consequences

- The expected saving is the removed LLM reading call minus classifier overhead. The old
  reading took about 3.5 s in the cloud and 0.8 s locally; the integrated adapter later measured
  261.5 ms median on its specified synthetic multi-sentence inputs. Complete voice-turn latency
  and independent precision remain to be verified.
- One more model to version: its labels, training script, threshold and ONNX export. A change to
  the labels or the base model means retraining and measuring again.
- The labels are synthetic, come from one labeller and cover development professions only. Use
  in releases needs a check on the independent cards and on real voice transcripts, where
  recognition errors change the wording.
- The backend image gains a few tens of MB of runtime libraries; the `models` volume gains
  about 342 MB including its tokenizer.
- The first load from a cold volume took 137 s in the pilot. The backend remains responsive
  while loading; an interview configured to use Laya must wait for it to become ready.

## Alternatives considered

- **Reading the limits concurrently with the decision.** It saves the same time without a new
  model, but the decision no longer sees the limits.
- **Laya for the move decision.** It was measured and not adopted: it stayed at or below simple
  state features, and below the agreement between two labellers.
- **PyTorch in the backend.** It was about 2.5 times slower than ONNX on CPU in the pilot and
  adds more than a gigabyte to the image.
- **A smaller encoder.** Not measured. It would need its own labelled evaluation; Laya was chosen
  because its multilingual encoder is already licensed for this use.
