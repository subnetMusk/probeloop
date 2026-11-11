# Guided installer validation — 2026-11-11

This record concerns distribution and installation behaviour. Interview quality, independent
stated-limit accuracy and physical Mac performance remain separate [acceptance gates](../status.md).

## Artifact and automated checks

Validated [v0.1.0-alpha.2](https://github.com/subnetMusk/probeloop/releases/tag/v0.1.0-alpha.2),
built from `ba26426`, through the [release workflow](https://github.com/subnetMusk/probeloop/actions/runs/42943829144).
The ZIP downloaded anonymously and matched SHA-256
`98d7e8b65aa90940666347a2e141f01c5e6bd9abaa0b63629337f9bbc164c805`.

- 620 backend tests passed; 38 PostgreSQL variants ran separately and passed. The normal run
  skipped those variants and deselected 23 live tests.
- Ruff, strict mypy, all 10 import contracts, generated API types and installer/documentation
  contracts passed.
- 77 frontend unit tests and 21 scripted browser scenarios passed; two opt-in live-provider
  browser scenarios were skipped.
- All three runtime images built and passed native checks on amd64 and arm64. Anonymous access
  to each ZIP-pinned OCI index confirmed both Linux platforms.

ARM64 checks cover dependency imports and a synthetic ONNX int8 CPU kernel. The actual downloaded
speech and classifier models below ran on amd64. This is not a physical Mac benchmark.

## Empty installation with the published package

The host was Windows with Docker Desktop using Linux containers, exposing 24 CPUs and about
7.7 GiB to Docker. The published Windows PowerShell launcher ran with isolated empty data/model
volumes and port 8011. Its browser-opening call was intercepted to verify the emitted URL;
browser rendering was covered separately by Playwright. No host Python, Node, Git or Make was
used to launch or configure this package.

Before weights were present, the app opened with cloud processing proposed, unavailable local
LLMs disabled, setup unfinished and Whisper off. The base-install API requested only Parakeet,
Piper Serena and Laya. Every download job completed successfully with verified model files.

| Observation | Result |
|---|---|
| Download jobs, including verification and activation notification | 541.02 s |
| Model setup through engine readiness and voice preview | 605.07 s |
| Parakeet, Piper and Laya | Installed and available |
| Whisper | Disabled; files absent |
| Local LLMs | Unavailable; none requested or downloaded |
| Provider selection after model installation | Remained cloud; no automatic switch to Laya |
| Container IDs and start times | Unchanged; zero restarts for all four services |
| Voice preview | Actual Piper WAV, 99,884 bytes |

Timings are one network-dependent installation observation, excluding image download/extraction.
They are neither per-turn inference latency nor an expected duration on other hardware.

## Recovery and remaining scope

An earlier alpha.1 test installed and activated all models but exposed a false failed-job state
when speech warm-up delayed the reload acknowledgement. Alpha.2 makes that notification best
effort. Both HTTP-unavailable and timeout responses have regression coverage; verified downloads
remain successful while consumers report their separate readiness.

Contracts also exercise interrupted/resumed transfers, valid-file reuse, insufficient space,
incorrect checksums, unavailable local providers, frozen tools and guarded configuration changes.
Temporary installation volumes were removed after verification. Existing application data and
model volumes were preserved. Local recordings and independent real interviews were not part
of this installation test.
