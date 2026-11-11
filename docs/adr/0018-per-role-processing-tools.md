# 0018 — Select processing tools per role in Settings

- Status: Accepted
- Date: 2026-11-10

## Context

The uniform local/cloud execution profile cannot express a local classifier alongside cloud
interviewing, or different providers for analysis and reports. Choosing a provider inside every
interview preparation also repeats a server setting in the interview form.

## Decision

Settings owns four choices: interviewer, document analysis, evaluation and stated-limit reading.
The first three support the configured local LLM and ChatGPT; stated-limit reading also supports
the approved Laya classifier. Speech recognition and synthesis remain local.

Availability comes from the actual adapters. Local model checks describe the configured Ollama
model without loading it, ChatGPT requires an account with plan access, and Laya requires a
checksum-verified, loaded model. Unavailable choices stay visible but disabled, and the API
rejects unsupported or unavailable selections. The dashboard shows the current selections.

The application stores a frozen, versioned execution plan with new preparations, interviews and
job payloads, using the existing execution-profile field. A migration widens its two database
columns to text. Legacy `local` and `cloud` values still mean a uniform plan. Mixed plans are
self-contained JSON, so database backups preserve their meaning independently of machine
settings. The domain continues to carry an opaque string; the routing adapter interprets it.

Only the composition root chooses adapters. Application use cases consume `ChatModel` or
`StatedLimitReader`; they do not import ONNX or tokenizer libraries. Context-local job scopes
and pinned interview adapters apply each role's frozen selection.

Selections cannot change while an interview is connected or work is pending. A provider error
pauses an interview without switching tools or producing a substitute question. A classifier
error follows the same rule. The user restores the selected tool and explicitly resumes. The
existing validation of generated structured content stays separate from provider availability.

## Consequences

- New work uses server defaults without a provider selector in the preparation wizard.
- Existing work keeps its plan when the defaults later change.
- Reauthentication remains possible without changing the selected provider.
- Missing tools are reported rather than replaced with a provider that sends data elsewhere.
- Downgrading the database to the uniform-profile schema is refused while mixed plans exist.
