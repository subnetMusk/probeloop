# 0010 — Speech synthesis: Piper in its own container

- Status: Accepted for the engine. The default Italian voice is pending a listening test.
- Date: 2026-11-06

## Context

Italian text-to-speech must start playing quickly (at most 600 ms for a sentence of about 15
words) and run on the CPU, because the GPU is reserved for the LLM. The good Italian options all
involve GPL components (ADR 0007).

M1 measured Piper 1.8.0 over its HTTP server, in a separate container:

| Voice | Latency p50 | RTF |
|---|---|---|
| it_IT-serena-medium | 0.16 s | 0.03 |
| it_IT-paola-medium | 0.42 s | 0.08 |
| it_IT-riccardo-x_low | 0.13 s | 0.03 |

## Decision

- Piper runs as the `tts-piper` service: unmodified `piper-tts`, its built-in HTTP server
  (`/synthesize`), and voices stored in the `models` volume.
- The backend synthesises one sentence per request and streams the sentences to the browser.
- The default voice is chosen between serena-medium and paola-medium after a listening test.
  riccardo is an `x_low` (16 kHz) voice and is not a default candidate.

## Consequences

- All voices meet the latency threshold with wide margin, and RTF is far below 1.
- The GPL component stays outside the ProbeLoop process.
- The voice licenses (CC0 for paola, CC-BY-4.0 for serena) must be shown in the UI and the
  documentation.

## Alternatives considered

- **Kokoro** — weak Italian voices (grade C), and Italian G2P goes through espeak-ng (GPL).
- **Chatterbox Multilingual and Qwen3-TTS** — too heavy for the CPU on machine A, and not suited
  to Turing GPUs.
- **Browser Web Speech** — deferred. Its timing and events are unreliable, and its quality
  depends on the operating system.
