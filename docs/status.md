# Current implementation and acceptance status

Updated for the guided-installation release, 2026-11-11. This page describes current behaviour;
dated research and handoffs retain the measurements available at their original checkpoints.

The [alpha.2 installation validation](research/installation-validation-2026-11-11.md) records
published-artifact checks, the empty-volume Windows run and the limits of ARM64 evidence.

## Implemented

- Reviewed document context, source-linked facts and confirmed profession, role and seniority.
- Adaptive text and voice interviews, follow-ups and per-session execution plans.
- Separate per-role processing tools in Settings, availability checks and home-page summaries.
- Local ONNX stated-limit reading with Laya; interview decisions remain with the selected LLM.
- Guided first run, model provisioning with hashes and progress, optional Ollama model pulls.
- Local Parakeet recognition and Piper synthesis; optional Whisper second transcription.
- Correctable transcripts with revision history, report exports, history and portable backups.
- Evidence-scoped reports with descriptive anchors shown on a 0–100 scale and unassessed criteria.
- Container-based tooling, import contracts, adapter contracts and scripted browser acceptance.
- Versioned installer packaging for amd64/arm64 images and OS-native shell launchers.

## Remaining quality gates

- Interview behaviour and evaluator grounding across independent professions, seniority and
  difficult answers. An automated green suite is not an interviewing-quality benchmark.
- Speech-recognition accuracy and hallucination/omission behaviour on representative real
  recordings, including specialist terms and realistic microphone conditions.
- Independent stated-limit examples and real ASR transcripts. The Laya pilot used synthetic
  development data and label-derived thresholds; it is a provisional model, not a final release.
- Physical Mac latency, memory use and usability with Docker Desktop. Native ARM64 builds and
  dependency/model smoke tests establish narrower compatibility evidence, not a Mac benchmark.
- Voice preference/listening acceptance and complete real voice interviews after each relevant
  model or orchestration change.

## Reading measurements

The [Laya pilot](research/laya-limits-pilot.md) reports held-out-profession recall of 288/294
limit-containing answers and 8/312 false alarms at threshold 0.5. Those are synthetic pilot
results. The integrated adapter benchmark later measured about 261.5 ms median for its specified
multi-sentence synthetic inputs, while the earlier isolated pilot measured about 125 ms under
different conditions. Neither is the complete voice-response latency or a physical Mac result.

The provisional full checkpoint, int8 runtime export, tokenizer and model card are published at
[submsk/probeloop-laya-stated-limits](https://huggingface.co/submsk/probeloop-laya-stated-limits).
Installers pin the reviewed revision and hashes; a later fine-tuning needs its own validation and
manifest update. Laya is not adopted for choosing interview moves.

The active product work remains the adaptive interview/reporting milestone and its acceptance
work. Guided installation is an explicitly approved usability addition. Web crawling and later
roadmap capabilities are not introduced by this release.
