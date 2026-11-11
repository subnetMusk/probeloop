# Guided installation checkpoint — 2026-11-11

This checkpoint records implementation and local validation. Read [current status](../status.md)
and [operations](../operations.md) for maintained product guidance.

## Delivered behaviour

The browser can start before any model is installed. The first-run page and Settings share
installation status, persisted download jobs, optional Whisper, voice preview and Ollama
connection/model management. A separate provisioner writes the shared model volume; consumers
are read-only. Downloads use pinned sizes and hashes, resume partial files and activate only
verified assets. Tools are chosen per role and frozen for each interview. Provider failures
pause the interview without changing provider; active work locks configuration changes.

The provisional fine-tuning is published at
[submsk/probeloop-laya-stated-limits](https://huggingface.co/submsk/probeloop-laya-stated-limits),
revision `4d8892cf85d84772b072b44e6db4515a6a6093f7`, tag `pilot-2026-11-10`.
Conversion to Safetensors preserved all 136 tensors exactly. Runtime installation downloads
only the int8 ONNX export and tokenizer, approximately 342 MB.

## Local evidence

- Backend: 616 tests passed, 38 PostgreSQL variants skipped locally, 23 live tests deselected.
  Later installer/API changes passed their 14 targeted tests; speech worker tests passed 18.
  Ruff, strict mypy and all 10 import contracts passed.
- Frontend: 77 unit tests passed, along with lint, architecture, formatting, type and bundle checks.
- Rebuilt browser application: 20 Playwright scenarios passed, with two opt-in live-provider
  scenarios skipped. These include first run, mobile settings, persisted progress, accessibility,
  unavailable tools, locked menus and the complete scripted voice/transcript/report workflow.
- A real Laya installation into an empty disposable model volume took 65.24 seconds for download
  and verification and 123.95 seconds until the classifier was available, without restarting.
- A scripted interview using that real classifier verified its provenance reference and locked
  tool settings. Its 532 ms move used scripted LLMs and is not a cloud latency measurement.
- The rebuilt primary application returned a real Piper WAV voice preview. Its existing cloud
  tool choices and enabled second transcription were preserved.
- Disposable-volume checks exercised root-owned legacy model directories and verified that the
  provisioner dropped to UID/GID 1000 before serving requests.

Ignored local evidence is under `var/test-run/installation/`. It is not application data to
restore or a benchmark dataset. Native ARM64 CI and the published installer are separate release
checks. Physical Mac performance and independent real-speech/interview quality remain open.

## Cold-start observation

During concurrent image builds, a cold existing Docker model volume loaded exceptionally slowly:
Parakeet took about 20 minutes on this Windows machine. There was no OOM; sampled execution was
waiting on model-file reads and checksums. The subsequent fresh-download test was much faster.
Do not replace the original pilot timings with this observation or claim a Mac benchmark.
Startup readiness is asynchronous and the interface remains available while models load.
