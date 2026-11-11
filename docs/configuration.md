# Configuration and processing tools

## User settings

Settings contain independent tool choices for interviewer, document analysis, evaluation and
stated-limit reading. The first three support ChatGPT or Ollama. The stated-limit reader also
supports the approved Laya ONNX classifier. Unavailable options are disabled, with a reason:
missing sign-in, missing model, loading, failed service, or unsupported turn mode.

The home page displays the current choices. New preparations and interviews retain their own
execution plan; the interview wizard does not ask for another processing profile. Legacy uniform
`local` and `cloud` plans remain readable. Mixed plans are versioned, self-contained JSON strings
inside the existing execution-plan fields; the UI presents names rather than raw JSON.

Tool, installation and account sign-out changes require no active interview or pending background
job. A selected provider failure pauses the interview without switching tools. Existing bounded
provider retries and structured-output validation repairs remain; malformed generated content and
provider disconnection are distinct cases. Resume checks the selected tools again.

## First run and machine settings

The Compose runtime connects the backend to an internal model provisioner. A fresh SQLite
installation proposes cloud tools, leaves Whisper refinement off, and opens guided setup. Existing
databases or saved execution selections are recognised as existing installations and retain their
selection and refinement behaviour. Advanced externally configured databases retain legacy defaults.

`installation.json` in the data volume persists setup completion, the refinement preference,
Ollama address and approved Laya download directory. It is machine configuration, separate from
portable user data. Changes apply while idle, without manually recreating the backend. The
classifier and speech worker notice newly installed models without a Docker restart.

Whisper runs only when refinement is enabled. Its model is downloaded on activation. Disabling
refinement retains recordings, transcript revisions and manual edits; it does not delete model
files. The report uses the current reviewed transcript revisions, including user corrections.

## Data flow

| Selection | Data sent to the tool |
|---|---|
| Cloud document analysis | Text from the supplied documents and the relevant preparation context |
| Cloud interviewer | Approved context, conversation text and state needed for the next move |
| Cloud evaluation | Transcript revisions and supporting context needed by the report |
| Cloud stated-limit reader | Latest question and answer text |
| Local Ollama | Corresponding text sent to the configured Ollama endpoint |
| Local Laya | Question/sentence pairs processed in the backend's CPU ONNX session |
| Local speech services | Audio for recognition; question text for synthesis, over the internal network |

The ChatGPT adapter uses the signed-in account's permitted plan capabilities. ProbeLoop does not
silently switch to a billed API, another account or another provider. Sign-in tokens remain in
the machine data volume and are excluded from portable backups. Recordings are not sent to the
cloud LLM by the current adapters. A remote Ollama address means the corresponding text leaves
the machine for that configured server.

## Runtime variables

The package works without editing environment files. Advanced source deployments can override
the supported Compose variables; see `compose.yaml` and `probeloop.settings.Settings` for defaults.

| Variable | Purpose |
|---|---|
| `PROBELOOP_OLLAMA_BASE_URL` | Initial native or remote Ollama address; persisted machine setting thereafter |
| `PROBELOOP_INTERVIEWER_MODEL` | Local interview model, also used for local stated-limit reading |
| `PROBELOOP_CLOUD_INTERVIEWER_MODEL` | Configured cloud interviewer |
| `PROBELOOP_CLOUD_ANALYSIS_MODEL` | Configured cloud document-analysis model |
| `PROBELOOP_CLOUD_EVALUATION_MODEL` | Configured cloud evaluation model |
| `PROBELOOP_CLOUD_REASONING_OFF` | Reasoning-effort value for calls requesting reasoning off |
| `PROBELOOP_INTERVIEWER_TURN` | `two_step` default; Laya requires this adaptive mode |
| `PROBELOOP_LIMITS_THREADS` | Classifier CPU threads; default 2, with idle spinning disabled |
| `PROBELOOP_LIMITS_MODEL_URL` | Initial approved, pinned public HTTPS model directory |
| `PROBELOOP_STT_THREADS`, `PROBELOOP_STT_CPUS` | Speech worker resource allocation |

Speech recognition uses six engine threads by default, without an explicit container CPU quota.
This allows the setup page to open when Docker Desktop exposes fewer than six CPUs. An optional
`PROBELOOP_STT_CPUS` quota must fit Docker's allocation; `0.0` leaves that quota unset, following
the [Compose CPU setting](https://docs.docker.com/reference/compose-file/services/#cpus).
| `PROBELOOP_TTS_VOICE` | Default Italian Piper voice identifier |
| `PROBELOOP_DATABASE_URL` | Optional PostgreSQL connection instead of default SQLite |
| `PROBELOOP_PORT` | Published loopback port in the installer bundle |

`Settings` does not read a host `.env` file itself. Compose reads `.env` for interpolation, then
passes only variables declared in its service environment. Settings not forwarded by Compose
(for example advanced local analysis/evaluation model or context-window overrides) need an
explicit `compose.override.yaml` environment entry. A machine setting already persisted through
the UI takes precedence over its initial environment default.

Do not commit `.env`, sign-in tokens, personal documents, recordings or model weights. Debug LLM
logging is off by default; enabling it writes sensitive local diagnostics and is for development.
