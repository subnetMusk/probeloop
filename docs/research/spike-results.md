# M1 spike results

> **Research and validation record.** Interpret measurements in their original conditions; they are not current runtime guarantees.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

- **Dates:** 2026-11-04 to 2026-11-06.
- **Machine:** Machine A, as described in the [initial research](2026-11-initial-research.md):
  - Windows 10 Pro, Ryzen 9 3900X, RTX 2070 Super 8 GB, 16 GB RAM;
  - Docker Desktop 29.8 with the WSL2 backend, which gives the Linux VM 7.7 GB of RAM;
  - Firefox and several desktop applications open, with about 1.2 GB of VRAM used at baseline.
- **Scripts and raw outputs:** the scripts are in [`spikes/`](../../spikes/). Raw outputs stay in
  the git-ignored `spikes/results/`.
- **Status:** all planned measurements are done except two, both pending on the repository owner:
  - **WER on real recordings.** Every STT number below uses synthetic Piper speech.
  - **The Italian voice listening test.**

## 1. Thresholds

| Threshold (roadmap M1) | Result | Verdict |
|---|---|---|
| LLM time to first token ≤ 1.5 s, warm, 4k prompt | 0.58–0.93 s with the prompt prefix cached (append-only layout); 3.5–4.7 s for a fresh prompt | **Pass** with the append-only layout and cache priming; fail without |
| LLM generation ≥ 25 tokens/s | 36–44 tokens/s at 4–5k context; 49–57 tokens/s at short context (8–9B) | Pass |
| No CPU offload at the chosen `num_ctx` | Native: 8k entirely on GPU, 16k offloads about 0.9 GB. Container: 8k offloaded 0.4–1.2 GB in two of four loads | Pass at 8k native; 16k rejected |
| STT turbo int8 on CPU, RTF ≤ 0.5 | 0.46–0.51 full pass | Borderline |
| Italian WER ≤ 10% | turbo 6–8%, Parakeet 12.6%, small 13–15% (synthetic speech) | turbo passes; real speech pending |
| STT tail p50 ≤ 2 s | Parakeet 0.38–0.43 s; turbo 10.9–13 s; small 1.8–2.5 s | **Parakeet only** |
| TTS first audio ≤ 600 ms (about 15 words) | Piper: paola 0.42 s, serena 0.16 s, riccardo 0.13 s (p50) | Pass |
| Interviewer move valid ≥ 95% | JSON constrained: 100% (90/90, three models); header + text: 76–95% | **JSON passes**, header fails |

## 2. LLM (Ollama)

### 2.1 Native (Windows, Ollama 0.40.13) versus containerised (WSL2, Ollama 0.40.14)

`qwen3.5:9b`, `think=false`, flash attention, `q8_0` KV cache.

| Measure | Native | Container |
|---|---|---|
| Cold load | 50 s* | 143 s (421 s during a concurrent download) |
| Reload when `num_ctx` changes | 8–10 s | 60–273 s |
| Prefill, warm | ~1090 tokens/s | ~1080–1490 tokens/s |
| Generation, 4–5k context | 42–44 tokens/s | 35–39 tokens/s |
| First token, 5k prompt, fresh | 4.7 s | 3.5–4.8 s |
| First token, 5k prompt, **append-only** | **0.70 s** | **0.58–0.93 s** |
| First token, 5k prompt, early prefix modified | 4.7 s | 3.6–5.0 s |
| VRAM at 8k | 5.65 GB, all on GPU | 5.1–5.6 GB on GPU, sometimes partial offload |
| At 16k | 0.93 GB on CPU, 31 tokens/s | 0.8–1.3 GB on CPU, 28 tokens/s |

\* The first native cold load ran while a container download was writing to disk.

**Findings**

- **The KV-cache prefix is reused with qwen3.5's hybrid architecture.** An append-only prompt cuts
  the first-token latency by 5–7×. Changing anything early in the prompt removes the benefit.
- **The containerised Ollama is as fast as the native one once warm, but loading models through
  the WSL2 VM is 3–15× slower and erratic.** During the runs the host had only 0.8–3 GB of free
  RAM. [I] The likely cause is memory pressure on a 16 GB host running both the VM and desktop
  applications.
- **16k context does not fit fully in 8 GB of VRAM.** 8k does, natively.

**Decision for machine A:** use the **native Ollama on the host**, reached from the Compose
services through `host.docker.internal`. The Compose `ollama` service (profile `nvidia`) stays
available for Linux hosts with enough RAM. This is the fallback foreseen in ADR 0008. It also
keeps the WSL2 VM's memory free for speech recognition and the backend, so `.wslconfig` needs no
change.

### 2.2 Interviewer move formats

Setup:

- 10 scripted interview states: opening, a vague answer, a detailed answer, a wrong technical
  claim, "I don't know", off-topic, unclear ownership, final question and closing.
- Short prompts (about 0.7–1k tokens), `num_ctx` 8192, temperature 0.7, top_p 0.8.
- n = 50 per format for `qwen3.5:9b` (native), n = 20 per format for the other two (container).

| Model | Format | Valid | First sentence p50 / p95 | Generation |
|---|---|---|---|---|
| qwen3.5:9b | header + text | 76% | 0.95 / 1.42 s | 57 tokens/s |
| qwen3.5:9b | JSON (constrained) | **100%** | 0.99 / 1.26 s | 57 tokens/s |
| ministral-3:8b | header + text | 95% | 1.02 / 1.26 s | 49 tokens/s |
| ministral-3:8b | JSON (constrained) | **100%** | 0.96 / 1.20 s | 49 tokens/s |
| qwen3.5:4b | header + text | 90% | 0.67 / 0.86 s | 74 tokens/s |
| qwen3.5:4b | JSON (constrained) | **100%** | 0.80 / 0.90 s | 71 tokens/s |

- **Constrained JSON respected the schema's property order in 90 of 90 moves**
  (`action, topic_id, utterance, covered_topic_ids`).
- **Incremental parsing of the partial JSON gives the first sentence as early as the plain-text
  format does.** The concern that JSON would delay the first sentence did not materialise.
- **Header failures** were missing `TOPIC`, or malformed lists such as `COVERED=t1,none`.

→ **ADR [0011](../adr/0011-interviewer-move-format.md): constrained JSON.**

### 2.3 Quality of the interviewer's Italian

This is a qualitative first-pass review of the JSON moves. The full outputs are in
`spikes/results/llm/quality_*.md`.

| Model | Strengths | Weaknesses |
|---|---|---|
| `ministral-3:8b` | Most natural Italian; consistent formal register ("Lei"); handles off-topic answers and the closing well | Occasional grammar slips; sometimes corrects the candidate (forbidden by the rules); sometimes asks two questions |
| `qwen3.5:9b` | Good overall | English words inside Italian sentences ("hai disagreed"); mixes "tu" and "Lei"; tends to move on after a vague answer instead of probing; one small invented detail ("grazie per essere arrivato in tempo") |
| `qwen3.5:4b` | Fastest | Visible grammar errors ("Le dettagli su il lavoro remoto"); mixed register; some odd questions |

**Behaviours common to all three models**, which need prompt work and evaluator tests in M2:

- they sometimes correct the candidate during the interview;
- they sometimes ask two questions in one turn.

**Proposed default:** `ministral-3:8b` for the interviewer, at `num_ctx` 8192.
- Its weights are 6.0 GB, against 6.6 GB for qwen3.5:9b, which leaves more VRAM headroom.
- It has no thinking mode, which the interviewer does not use anyway.
- `qwen3.5:9b` remains the alternative, and the candidate for the evaluator, where thinking may
  help (to be measured in M7).

The default requires pulling `ministral-3:8b` into the native Ollama. The download is about 6 GB.

## 3. Speech recognition (CPU, in a container)

**Audio.** Five synthetic answers of about 18 s each, generated with Piper (paola and serena). They
contain technical vocabulary (FastAPI, PostgreSQL, Redis, OR-Tools, EXPLAIN ANALYZE, Kafka). Each
also has 2 minutes of near-silence at about −60 dBFS.

**Live transcription simulation.**

- Silero VAD cuts a segment at pauses of 600 ms, or at a maximum segment length (`vad`).
- Each segment is transcribed as soon as it would have "arrived" in real time.
- The **tail** is the time between the end of the audio (the end-of-answer click) and the end of
  the last transcription.

**Runs on 2026-11-06** had `qwen3.5:9b` loaded on the GPU by the native Ollama. Settings:
`beam_size=1`, language `it`, a vocabulary `initial_prompt` for Whisper.

| Engine | CPUs | `vad` max | RTF full pass | Tail p50 / max | WER incremental / full | RSS |
|---|---|---|---|---|---|---|
| Parakeet TDT 0.6B v3 int8 (onnx-asr) | 8 | 15 s | 0.061 | **0.41 / 0.56 s** | 12.6% / 12.6% | 1.5 GB |
| Parakeet TDT 0.6B v3 int8 | 6 | 15 s | 0.066 | **0.38 / 0.53 s** | 12.6% / 12.6% | 1.5 GB |
| faster-whisper large-v3-turbo int8 | 8 | 15 s | 0.513 | 10.9 / 13.2 s | **6.2% / 8.2%** | 1.8 GB |
| faster-whisper large-v3-turbo int8 | 8 | 8 s | 0.460 | 12.1 / 16.1 s | 7.9% / 8.2% | 1.7 GB |
| faster-whisper large-v3-turbo int8 | 6 | 8 s | 0.484 | 13.0 / 17.1 s | 7.9% / 8.2% | 1.7 GB |
| faster-whisper small int8 | 8 | 15 s | 0.378 | 2.5 / 15.1 s | 13.3% / 13.3% | 1.1 GB |
| faster-whisper small int8 | 8 | 8 s | 0.320 | 1.8 / 11.1 s | 15.3% / 12.9% | 1.1 GB |

The Whisper rows for `vad` 15 s were measured on 2026-11-04 without an LLM loaded.

**Findings**

- **Whisper is unsuitable for live incremental transcription on this CPU.**
  - Each call processes a fixed 30 s window, so a short segment costs almost as much as a long one,
    and shorter segments make the tail *worse* (12–13 s at 8 s against 10.9 s at 15 s).
  - turbo is still the most accurate engine. Its vocabulary prompt got technical terms right, for
    example "EXPLAIN ANALYZE".
- **Parakeet** has a sub-second tail and does not care about the CPU limit (6 or 8). With no
  prompt biasing, however, it gets technical terms wrong: "EXPLAIN ANALYZE" became
  "Esplanalizia", and it sometimes drops short words.
- **small** produced CJK garbage on one file, and has the worst WER.
- **Silence.**
  - With VAD, no engine produced text on silence.
  - Without VAD, turbo produced "Grazie." on 30 s of silence.

  The VAD gate and the blocklist from the architecture are therefore necessary.
- **Maintenance issue.** faster-whisper 1.2.1 is incompatible with PyAV 19, which no longer
  accepts the `metadata_errors` argument. It needs `av<17`, and the spike pins `av==16.0.1`. This
  confirms the maintenance risk noted in the research.
- **Download times.** The first model downloads from Hugging Face without a token took 7–11
  minutes.

→ **ADR [0009](../adr/0009-speech-recognition.md):**
- Parakeet for live transcription.
- faster-whisper turbo as a post-interview refinement pass with vocabulary biasing.

The post-interview pass produces the transcript the user reviews and the evaluator uses. At RTF
about 0.5 it takes about 7–8 minutes for a 15-minute interview on 8 CPUs.

**Pending: WER on real recordings** (`spikes/inputs/recording_script_it.md`). Synthetic Piper speech
is cleaner than a real voice, so absolute WER values will rise. What has to be confirmed is the
ranking and Parakeet's usability for the live view.

## 4. Speech synthesis (Piper 1.8.0, CPU, separate container)

The sentences are interviewer questions of 13–16 words. Synthesis is per sentence over HTTP
(`/synthesize`), after a warm-up.

| Voice | Latency p50 / max | RTF |
|---|---|---|
| it_IT-paola-medium | 0.42 / 0.45 s | 0.081 |
| it_IT-serena-medium | 0.16 / 0.20 s | 0.034 |
| it_IT-riccardo-x_low | 0.13 / 0.23 s | 0.025 |

All voices meet the threshold. **Pending: a listening test by the repository owner.** The samples
are in `spikes/results/tts/sample_*.wav`. riccardo is an `x_low` (16 kHz) voice, so serena or
paola is expected.

→ **ADR [0010](../adr/0010-speech-synthesis.md)**, accepted for the engine. The default voice is
pending the listening test.

## 5. Latency budget implied for M3

This is an estimate of the end-of-answer → first-audio path at p50 on machine A. [I]

| Step | Time |
|---|---|
| Parakeet tail | ~0.4 s |
| LLM first sentence of the utterance: first token 0.6–0.9 s with an append-only prompt, plus about 0.6 s of generation | ~1.2–1.6 s |
| Piper first sentence | ~0.2–0.4 s |
| Network, framing and playback scheduling | ~0.1–0.2 s |
| **Total** | **about 1.9–2.6 s** |

This is within the M3 target of p50 ≤ 4 s and p95 ≤ 7 s. The main risks are:

- a cache miss, which adds about 3 s;
- an LLM reload, which must never happen during a session.
