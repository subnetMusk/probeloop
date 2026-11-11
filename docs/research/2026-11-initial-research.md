# Initial technical research (2026-11)

> **Research and validation record.** Interpret measurements in their original conditions; they are not current runtime guarantees.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

- **Date:** 2026-11-03.
- **Scope:** reuse of existing projects, local LLMs, speech engines, realtime transport, frontend
  tooling and a future OpenAI integration.

Every claim carries one of these markers:

| Marker | Meaning |
|---|---|
| **[D]** | Documented; a source is given |
| **[I]** | Inferred |
| **[V]** | To be verified experimentally (milestone M1 or later) |

Versions and facts are as of the date above; re-check them before relying on them.

**Development hardware**
- **Machine A:** Windows 10 Pro 19045, Ryzen 9 3900X, RTX 2070 Super 8 GB (Turing, sm_75), 16 GB RAM,
  NVIDIA driver 616.92, Docker Desktop with the WSL2 backend.
- **Machine B (future):** MacBook Air M2 with 8 GB of RAM, using a remote LLM.

## 1. HackerRank hiring-agent

Repository: <https://github.com/interviewstreet/hiring-agent>, analysed at commit `e0ece80`.

### Facts

- **License.** The repository is MIT, but `pymupdf_rag.py` is code vendored from PyMuPDF4LLM under
  **AGPL-3.0-or-later**. The runtime dependencies `pymupdf` and `pymupdf4llm` are AGPL or
  commercial. The code base as it runs is therefore not purely MIT. [D]
- **What it is.** A batch CLI: PDF → Markdown (layout-aware, no OCR) → six section-by-section LLM
  calls → a `JSONResume` Pydantic model → a rubric-based score → CSV. [D]
- **Engineering.** No tests, no CI and no packaging (only `requirements.txt`). Configuration is
  global and loaded at import time, paths are relative to the working directory, and all I/O is
  synchronous. [D]
- **LLM providers.** Ollama, Gemini, OpenAI and Anthropic, all through an OpenAI-compatible
  `/chat/completions` client. The JSON Schema is passed as `response_format`. Pydantic validation
  runs only on the final result, not per section. [D]
- **GitHub analysis.**
  - Data: profile, repositories and per-repository contributors (N+1 requests).
  - Rate limiting: it can block with `sleep` for up to an hour.
  - It reads no READMEs, commits or language breakdowns.
  - Issue #424: classification data never reaches the evaluator. [D]
- **Prompt injection.** No mitigation. Two open issues document the risk:
  - #273: hidden white-on-white text in a PDF inflated a weak CV to a score of 91;
  - #452: forged data markers in a GitHub bio. [D]
- **Scope.** No job offer is taken as input; a "role" is a hand-written rubric. It is **not an
  interview-conducting framework**: no dialogue, no session state, no audio. [D]

### Reuse verdict

| Area | Decision |
|---|---|
| Structured CV extraction | Reference only. Worth keeping: the JSON Resume Pydantic subset, the section-by-section approach, and the anti-hallucination rules in `prompts/templates/basics.jinja`. |
| GitHub analysis | Rewrite, using its classification heuristic and project-selection prompt only as references. |
| Skills and experience | Reference only, for rubric wording. |
| Job-offer matching | Not useful. |
| As a dependency | No. |

The pattern worth reusing as an idea: dynamic Pydantic rubric models (`create_model` with
`Literal` values) and totals computed in code rather than by the model. If any MIT code is ever
copied, its copyright notice goes into a `THIRD_PARTY_NOTICES.md` file.

## 2. Ollama

### API and runtime

- **Versions.** Latest release 0.40.14 (0.40.13 installed). Official Python client `ollama` 0.6.3,
  MIT, with `AsyncClient`. [D] <https://github.com/ollama/ollama/releases>,
  <https://pypi.org/project/ollama/>
- **Native `/api/chat`.** [D] <https://docs.ollama.com/api/chat>,
  <https://docs.ollama.com/capabilities/structured-outputs>,
  <https://docs.ollama.com/capabilities/tool-calling>,
  <https://docs.ollama.com/capabilities/thinking>
  - NDJSON streaming.
  - `format` accepts a JSON Schema and constrains decoding.
  - Tool calling, also while streaming.
  - `think` accepts true, false or a level.
  - `keep_alive`.
  - Undocumented: which JSON Schema keywords are supported, and how `format` and `think` interact. [V]
- **Capability discovery.** `/api/show` and `/api/tags` expose `capabilities`, `context_length` and
  the thinking levels. [D, local]
- **Default context length depends on VRAM: 4096 below 24 GiB.** It must be set explicitly
  (`options.num_ctx` or `OLLAMA_CONTEXT_LENGTH`). [D] <https://docs.ollama.com/context-length>
- **The OpenAI-compatible `/v1` endpoints cannot set the context size per request.** [D]
  <https://docs.ollama.com/api/openai-compatibility>
- **Concurrency and memory.** [D] <https://docs.ollama.com/faq>
  - `OLLAMA_NUM_PARALLEL` defaults to 1.
  - `OLLAMA_MAX_LOADED_MODELS` defaults to 3 per GPU.
  - KV-cache quantisation (`OLLAMA_KV_CACHE_TYPE=q8_0`, which needs flash attention) roughly halves
    KV memory.
- **Speech.** Ollama now exposes `/v1/audio/transcriptions` and `/v1/audio/speech`. `lfm3-audio`
  (2B, 18 languages including Italian, LFM Open License) does both STT and TTS. [D]
  <https://docs.ollama.com/capabilities/speech>, <https://ollama.com/library/lfm3-audio>
  Quality, endpoint integration and license terms are unverified. [V]

### Models

**`qwen3.5:9b`** [D] (local `ollama show`), <https://ollama.com/library/qwen3.5>,
<https://huggingface.co/Qwen/Qwen3.5-9B>
- 9.7B parameters, Q4_K_M quantisation, 6.6 GB, 262144-token context.
- Tools, vision, and thinking (enabled by default).
- Apache-2.0.
- The installed presets (temperature 1, top_p 0.95) are the thinking settings. Qwen recommends
  temperature 0.7 and top_p 0.8 without thinking.
- Italian is not explicitly listed among the supported languages. [V]
- Hybrid attention / linear-attention architecture. [D] How much of a cached prompt prefix Ollama
  reuses with it is unknown. [V]

**VRAM.** About 1.2 GB of the 8 GB is already used by the desktop, leaving roughly 7 GB for a
6.6 GB model. [D, local] Expect partial CPU offload as the context grows. [V]

**Candidates for 8 GB** [D]:

| Model | Size | Notes |
|---|---|---|
| `qwen3.5:9b` | 6.6 GB | Installed |
| `ministral-3:8b` | 6.0 GB | Italian explicitly supported, no thinking. <https://ollama.com/library/ministral-3> |
| `qwen3.5:4b` | 3.3–4 GB | Leaves room for GPU speech recognition |
| `gemma4:e4b` | 6.6–9.5 GB | Configurable thinking; whether it fits is unverified [V] |

## 3. LLM abstraction libraries

| Option | Version and status [D] | Verdict |
|---|---|---|
| Own thin port with native SDKs (`ollama`, later `openai` 3.x) | Mature, MIT and Apache-2.0 | **Chosen.** Full access to `num_ctx`, `think`, `keep_alive` and `/api/show`, a small surface, and trivial fakes. |
| pydantic-ai 2.65 | MIT; very fast release cadence (2.0 shipped 2026-06) | Uses Ollama through `/v1`, losing per-request `num_ctx`. Possible future adapter for complex agent loops. <https://pydantic.dev/docs/ai/models/ollama/> |
| LiteLLM 1.106 | MIT. **Versions 1.82.7–1.82.8 were compromised on PyPI on 2026-03-24.** | Rejected: heavy, supply-chain risk, no benefit with two providers. <https://www.netspi.com/blog/executive-blog/ai-ml-pentesting/litellm-supply-chain-compromise/> |
| instructor 1.17 | MIT; structured output only | Not needed. |

While this research was being done, a documentation page in this area contained a hidden
instruction aimed at AI agents (asking them to add tracking parameters to URLs). It was ignored.
It is a concrete example of the kind of content the crawler must treat as data.

## 4. Speech recognition (STT)

### faster-whisper

- **Releases.** Latest 1.2.1 (2025-10-31), with **no release for 12 months**: a maintenance risk.
  CTranslate2 is active: 4.8.5 (2026-11-02) has Windows x64, macOS arm64 and Linux wheels. [D]
  <https://pypi.org/project/faster-whisper/>, <https://pypi.org/project/ctranslate2/>
- **GPU libraries.** It requires cuBLAS for CUDA 12, plus cuDNN 9 for older CTranslate2 versions.
  CTranslate2 4.6.3 made cuDNN optional. [D] [V]
  - On Windows the pip `nvidia-*` route is documented as Linux-only. **Inside a Linux container the
    pip wheels work**, and the GPU is reached via WSL2. [V in M1]
    <https://github.com/SYSTRAN/faster-whisper>
- **Turing GPUs** support `float16`, `int8_float16` and `int8`; `bfloat16` falls back to float32.
  [D] <https://opennmt.net/CTranslate2/quantization.html>
- **macOS:** CPU only (no Metal backend). [D]
- **Built in:** Silero VAD v6 (`vad_filter`), word timestamps, and PyAV with bundled FFmpeg. [D]
- **Memory and speed** (13-minute file, beam 5) [D]:
  <https://github.com/SYSTRAN/faster-whisper/issues/1030>

| Model | VRAM fp16 | VRAM int8 | Time fp16 |
|---|---|---|---|
| large-v3 | 4.5 GB | 3.0 GB | 52 s |
| large-v3-turbo | 2.5 GB | 1.5 GB | 19 s |

- **Italian WER on FLEURS** (third-party, whisper.cpp at Q8): large-v3 2.54, turbo 2.77, medium
  4.17, small 7.97. [D] <https://models.handy.computer/languages/it>
- **Distil models are English-only.** [D]

### Alternatives

- **Parakeet TDT 0.6B v3** (CC-BY-4.0, 25 European languages including Italian).
  - Italian WER: FLEURS 3.00, CoVoST 3.69, MLS 10.08. [D]
    <https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3>
  - Runs without NeMo through `onnx-asr` 0.12 (MIT; Windows, macOS, Linux), which reports RTFx 36 on
    a desktop CPU. Inputs are limited to 20–30 s, so a VAD is needed. [D]
    <https://pypi.org/project/onnx-asr/>
  - `parakeet-mlx` runs it on Apple Silicon. [D]
  - There is no prompt or hotword biasing. [I]
- **Qwen3-ASR 0.6B/1.7B** (Apache-2.0): Italian WER 5.19 / 2.68. [D]
- **mlx-whisper** 0.4.3: Metal on a Mac. [D]
- **Rejected:**
  - Voxtral Mini Realtime (needs at least 16 GB);
  - SimulStreaming (at least 10 GB of VRAM, torch only);
  - Kyutai STT (no Italian);
  - WhisperLive and RealtimeSTT (unnecessary given the approach below). [D]

### Containerised speech servers

| Server | License and status | Missing for our use |
|---|---|---|
| Wyoming (`wyoming-faster-whisper` 3.8.1, `wyoming-piper` 2.5.2) | MIT, OHF-maintained, 2026 releases [D] | A per-request prompt (the prompt is global) and per-word confidences [I] |
| speaches | MIT, actively developed; latest release v0.9.0-rc.3 (2025-12) [D] | Still a release candidate |

**Decision:** an own minimal worker. Both remain possible alternative adapters.

### Approach and estimates

**VRAM contention.** A 6.6 GB LLM plus turbo (1.5–2.5 GB) plus a CUDA context exceeds 8 GB. [I]
→ On machine A, **speech recognition runs on the CPU and the GPU stays with the LLM.**

**Progressive transcription** [I]:
1. The server receives PCM audio.
2. Silero VAD closes a segment at pauses of about 600 ms, or force-cuts it at about 15 s.
3. Each closed segment is transcribed with the language fixed and an `initial_prompt` made of the
   committed text plus the snapshot vocabulary.
4. On the end-of-turn click, only the remaining tail is transcribed.

**Latency for a 60 s answer** [I, all V]:

| Engine | Full pass | Tail after the click (incremental) |
|---|---|---|
| turbo int8 on a 3900X CPU | 15–25 s | 0.5–3 s |
| small int8 on CPU | 4–8 s | |
| Parakeet on CPU | 2–4 s | |
| turbo on GPU | 2–4 s | |

## 5. Speech synthesis (TTS)

| Option | License [D] | Italian [D] | Verdict |
|---|---|---|---|
| **Piper** (`piper-tts` 1.8.0, OHF-Voice/piper1-gpl) | **GPL-3.0-or-later**; the old MIT rhasspy/piper is archived; the maintainers are looking for help | paola medium (CC0), serena medium/high (synthetic dataset, CC-BY-4.0), riccardo x_low | Fast on CPU (RTF about 0.15, secondary source). Has a built-in HTTP server. **Run as a separate program in its own container.** |
| Kokoro-82M / kokoro-onnx | Apache-2.0 / MIT | `if_sara` and `im_nicola` rated **C**; Italian G2P goes through espeak-ng (GPL) | Good for English, weak for Italian |
| Chatterbox Multilingual v3 | MIT, with a watermark on every output | Yes | Heavy (pinned torch, transformers, gradio); a future quality candidate |
| Qwen3-TTS 0.6B | Apache-2.0 | Yes, no native voice | Designed for bf16 and FlashAttention-2, which Turing lacks |
| XTTS-v2, F5-TTS | Non-commercial | — | Excluded |
| Orpheus es_it | Research release, 3B, gated | Yes | Excluded |
| Web Speech API (`localService === true` voices) | OS voices | Depends on the OS | Future zero-dependency fallback. Chrome's "Google" voices are remote and must be excluded. |

**GPL note** (not legal advice): importing a GPL module creates a combined work, while pipes,
sockets and command-line invocation normally keep programs separate. [D]
<https://www.gnu.org/licenses/gpl-faq.html> Hence Piper runs in its own container, reached over
HTTP.

## 6. Realtime transport and frontend

- **FastAPI WebSockets** handle text, JSON and binary frames. [D]
  <https://fastapi.tiangolo.com/advanced/websockets/> With explicit turn-taking and no barge-in,
  **one WebSocket per session** (binary PCM plus JSON events) is the simplest adequate design. [I]

**Voice-agent frameworks** [D]:

| Framework | Status | Verdict |
|---|---|---|
| Pipecat 1.15 | BSD-2; integrates Ollama, Whisper and Piper | Its frame pipeline would shape the domain, and push-to-talk has open bugs (#4707). Revisit for VAD or barge-in. |
| FastRTC 0.0.34 | Inactive since 2025-11 | Rejected |
| LiveKit Agents | Needs a LiveKit server | Rejected |

**Browser audio.**
- Capture with an AudioWorklet, downsampling to 16 kHz mono PCM16. [I]
- MediaRecorder (webm/opus) chunks after the first lack the container header, so they do not suit
  incremental decoding. [I]
- Play back by scheduling PCM chunks on the `AudioContext` clock. [I]

**Frontend versions** [D, npm]:

| Package | Version | Notes |
|---|---|---|
| Vite | 8.3 | Needs Node `^20.19` or `>=22.12`; Node 20 is end-of-life, so use Node 24 or 26 LTS |
| React | 19.3 | |
| Tailwind CSS | 4.3 | |
| shadcn CLI | 4.23 | Default primitives are Base UI since 2026-07; Radix is available via `-b radix` |
| TanStack Query | 5.x | |
| TanStack Router | 1.170 | |
| Zustand | 5 | |
| react-hook-form | 7.91 | |
| zod | 4.6 | |
| TypeScript | 7.0 | Native compiler; compatibility with typescript-eslint and Vite plugins is unchecked [V] |

## 7. OpenAI integration (future; not to be implemented now)

**"Sign in with ChatGPT"** is an official route, currently in preview. [D]
<https://developers.openai.com/siwc/token-sharing-open-source>,
<https://learn.chatgpt.com/docs/sign-in-with-chatgpt>

- **Eligibility.** Available to Plus and Pro subscribers, for open-source and locally run personal
  apps. Paid or remotely hosted apps must apply.
- **Sign-in.** OIDC with PKCE and no client secret. The callback is a **loopback
  `http://127.0.0.1:<port>`** address.
- **Requests.** The OAuth token is used as a bearer token on the Responses API, and usage counts
  against the plan's limits.

**Preview limitations:**
- `store:false` and `stream:true` are mandatory;
- **system-role messages are rejected**;
- `temperature`, `top_p` and `max_output_tokens` are not allowed;
- there is no server-side state;
- **there is no audio or transcription**;
- structured outputs are undocumented [V].

Reusing Codex CLI credentials in another app is not documented as allowed, so it is out.

**Design consequences:**
- `ChatRequest` keeps instructions separate from messages.
- `ModelCapabilities` includes `sampling_params` and `system_role`.
- Structured output must be able to degrade to "JSON in the prompt + validation + retry".
- Speech stays local.

## 8. Python tooling [D, PyPI]

| Tool | Version | Notes |
|---|---|---|
| uv | 0.13.7 | |
| FastAPI | 0.162 | |
| Pydantic | 2.14 | |
| SQLAlchemy | 2.1.7 | Needs Python 3.11 or later |
| Alembic | 1.20 | |

The native dependencies checked (ctranslate2, onnxruntime, PyAV, piper-tts) have Python 3.13
wheels. **Python 3.13** is therefore the baseline. Heavy optional engines (Chatterbox, torch-based
Kokoro) would run in their own images and do not constrain it.
