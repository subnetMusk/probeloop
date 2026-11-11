# 0009 — Speech recognition: Parakeet live, Whisper turbo refinement

> **Decision record.** Current implementation guidance is in [architecture](../architecture.md) and [configuration](../configuration.md); later ADRs amend specific decisions.
> ADR 0019 makes the second Whisper transcription optional and off on new installations. Existing installations preserve their preference; real-recording accuracy remains an open gate.

- Status: Accepted (WER on real recordings to be confirmed)
- Date: 2026-11-06

## Context

The end-of-answer → first-audio latency target is p50 ≤ 4 s. Transcription errors must not leak
into the evaluation. On machine A the GPU is taken by the LLM, so speech recognition runs on the
CPU in the `stt-worker` container.

The M1 measurements used synthetic Italian speech with an LLM loaded on the GPU (see
`docs/research/spike-results.md`):

| Engine | Tail after the click (p50) | WER | RTF full pass |
|---|---|---|---|
| faster-whisper large-v3-turbo int8 | 11–13 s | 6–8% | ~0.5 |
| Parakeet TDT 0.6B v3 int8 (onnx-asr) | 0.4 s | 12.6% | 0.06 |
| faster-whisper small int8 | 1.8–2.5 s | 13–15% | ~0.35 |

- **turbo** is the most accurate engine, and its vocabulary prompt fixes technical terms.
  Whisper's fixed 30 s window makes per-segment calls expensive, so it cannot keep up live.
- **Parakeet** has no prompt biasing.
- **small** also produced garbage text once.

## Decision

- **Live transcription:** Parakeet TDT 0.6B v3 (int8, via onnx-asr) on the CPU.
  - Segments are cut by Silero VAD at 600 ms pauses, with a maximum length of 15 s.
  - The text feeds the progressive transcript and the interviewer.
  - The interviewer prompt states that the transcript comes from speech recognition and may
    contain recognition errors, especially in technical terms.
- **Post-interview refinement:** a full pass with faster-whisper large-v3-turbo int8 on the CPU.
  - It uses VAD and an `initial_prompt` built from the context snapshot vocabulary.
  - It produces the transcript revision that the user reviews and that the evaluator uses.
  - It runs as a job when the interview ends, at about half the audio duration on 8 CPUs.
- **Engine identity on every revision.** Each transcript revision records the engine, the model
  and the settings that produced it.
- **Silence and hallucination guards are mandatory:**
  - VAD gating;
  - `condition_on_previous_text=False`;
  - a minimum segment length;
  - a blocklist of known hallucinated phrases.
- **GPU mode** (turbo `int8_float16` on CUDA) remains an option for when the LLM runs remotely.

## Consequences

- **Low live latency** (about 0.4 s of tail) and an accurate final transcript, at the cost of two
  engines in the worker image (about 1.5–1.8 GB of RAM each when loaded).
- **The review step waits for the refinement job.** For a 15-minute interview that is a few
  minutes on CPU. The UI must show progress.
- **Version pinning.** faster-whisper 1.2.1 needs PyAV below 17 (pinned to 16.0.1). This confirms
  the maintenance risk; the port keeps the engine replaceable.
- **Pending confirmation.** WER on real recordings may change the live/refinement split. The
  recording script is `spikes/inputs/recording_script_it.md`.

## Alternatives considered

- **turbo for live transcription** — the 11–13 s tail is far above target.
- **small for live transcription** — the worst WER, an unstable tail and an occasional
  hallucination.
- **Whisper on the GPU next to the LLM** — the VRAM is not sufficient.
- **Parakeet only** — technical terms are misrecognised without prompt biasing, which is exactly
  the error class that must not reach the evaluation.
