# 0019 — Guided installation and optional speech refinement

- Status: Accepted
- Date: 2026-11-11
- Amends: 0008, 0009, 0017, 0018

## Context

An end user with Docker Desktop should not need Python, Node, Make, git, manual model commands
or a local LLM. The primary laptop path uses ChatGPT plus local STT, TTS and Laya. Disk space is
limited, and the benefit of a second recogniser is not established on representative real audio.

## Decision

- Distribute versioned public GHCR runtime images for amd64 and arm64. Installer ZIPs pin their
  manifest digests and include Windows, macOS and Linux shell launchers. Source releases retain
  the repository's current visibility; public images do not make the source repository public.
- Open a first-run browser flow before any model download is required. New SQLite installations
  propose cloud processing; existing installations preserve their selection and refinement.
- Keep setup and model management in Settings. Availability, not a selected label alone, governs
  whether a tool may be selected. Installing Laya does not automatically change the selected reader.
- A dedicated internal provisioner owns model writes. It accepts approved asset identifiers,
  uses a versioned source/size/hash catalog, stages downloads, resumes parts where supported,
  verifies files and activates completed assets. Runtime consumers mount models read-only.
- Reuse persisted background jobs and the existing idle guard. Configuration and model operations
  cannot run through an active interview. No Docker socket is exposed to application services.
- Keep Ollama native and optional. Provide official host-install/configuration guidance, test its
  address and request its model downloads through the API. No privileged host installation runs
  from the browser or a container.
- Persist machine setup separately from portable data and account tokens. Apply idle configuration
  changes and newly installed models without manual Docker restarts.
- Leave Whisper second transcription off on new installations. Explicit activation downloads it
  and enables the post-call pass. Manual editing, recordings and revisions remain available.
- Do not replace transcription with automatic LLM rewriting. Correcting a candidate's substantive
  mistake would contaminate evaluation evidence. Alternative ASR needs independent comparison.
- Keep the provisional Laya artifact pinned. Its full training weights are for maintainers; the
  application downloads only the int8 ONNX and tokenizer.

## Consequences

The first model installation still needs disk space and internet access, and model loading may
continue after download verification. The app shows those states separately. Cloud processing
needs an eligible sign-in and sends the text required by the selected roles to that provider.
Consumer reload notifications are best effort. A temporarily unavailable speech worker retries
loading itself and must not cause a verified download job to be reported as failed.

Runtime images expose application code publicly; they contain no model weights or personal data.
Piper remains a separate GPL program, with its own source and licence obligations. The app does
not gain permission to install host services, control Docker or prune unrelated disk contents.

Native ARM64 CI evidence is reported separately from physical macOS performance. Research
quality gates remain open; installer completeness is not a claim of interviewer/ASR accuracy.
