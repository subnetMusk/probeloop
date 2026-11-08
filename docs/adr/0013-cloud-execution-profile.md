# 0013 — Optional cloud execution profile through Sign in with ChatGPT

- Status: Accepted
- Date: 2026-11-08

## Context

ProbeLoop is local-first ([ADR 0006](0006-single-user-local-first.md)). On machine A the
interviewer runs on `ministral-3:8b`, and analysis and evaluation on `qwen3.5:9b`. The small
local models limit the interviewer and the reports: they did not follow several evaluation rules
([ADR 0012](0012-interview-evaluation-pipeline.md)), and they carry technical misconceptions into
advice.

The owner asked for a second way to run the language models: ChatGPT, selectable from the UI,
**through the ChatGPT subscription and its usage limits, not pay-per-use API billing**. Speech
recognition (live and the refinement pass after the call) and speech synthesis stay local.

[ADR 0003](0003-llm-provider-port.md) prepared for this. Its `ChatModel` port keeps instructions
apart from messages and describes provider capabilities. The prompts were kept provider-neutral.

OpenAI documents ChatGPT plan usage for open-source and locally hosted apps
(<https://developers.openai.com/siwc/token-sharing-open-source>, read on 2026-11-08).

**Sign-in**

- OAuth authorization code with PKCE (S256), state and nonce.
- The redirect URI is a loopback `http://127.0.0.1:<port>/auth/callback`; only the port may vary.
- The scopes are `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct`.
  The last one is what allows plan usage.
- The resource is `https://api.openai.com/v1`.
- The first sign-in registers the app dynamically with `client_id=dynamic_agent_client`. The
  callback returns the issued client ID, which is used from then on. No client secret or API key
  is involved.
- Each installation sends an opaque, persistent host identifier.

**Tokens**

- Access tokens last one hour.
- Refresh tokens last 30 days and rotate, so refreshes must be serialised.
- Revocation goes through the endpoint published in the discovery document.
- Tokens must stay out of browser storage, URLs, logs and source control, in owner-only files.

**Inference**

- Requests go to `POST https://api.openai.com/v1/responses` with `store: false` and
  `stream: true`.
- Instructions go in `instructions`; system-role input items are rejected.
- `temperature`, `top_p` and `max_output_tokens` must be omitted.
- Plan errors include a usage limit, an ineligible account and temporary unavailability. They
  stop inference; OpenAI never switches to another billing path.

**Not documented for plan usage**

- Structured outputs (`text.format`).
- Reasoning effort.

**Eligibility**

- The client ID page says Sign in with ChatGPT "is currently offered to a select group of
  commercial partners", with a waitlist.
- The open-source pages describe dynamic registration without an approval step.
- Whether a non-partner open-source app is accepted is therefore unverified until the first
  real sign-in. An automated request to the authorization endpoint receives a Cloudflare bot
  challenge, so the check has to be done by the owner in a browser.

## Decision

**Adapter.** `ChatGptChatModel` implements the port over the Responses API with plain `httpx`. It
follows the preview rules:

- `store` false, `stream` true and `instructions`;
- no sampling parameters and no output cap.

**Structured output and reasoning.** They are requested: a strict JSON schema in `text.format`,
and the configured reasoning effort (`none` by default) when a request turns reasoning off.

- **When the provider rejects one of them as unsupported**, the adapter drops it for the rest
  of the process. A rejection is a 400 that names the parameter, or
  `subscription_sharing_unsupported_capability` without one. Without a schema, the response
  schema is appended to the instructions as a JSON format specification. The application layer
  validates every output anyway (ADR 0011).
- **Plan errors are mapped as follows.**
  - A usage limit or an ineligible account becomes `UserActionRequiredError`, whose message is
    shown to the user.
  - A rejected token is refreshed once, then reported as "sign in again".
  - Temporary unavailability is retried twice with backoff.

**Account.** `ChatGptAuth` implements the documented flow.

- **Credentials.** The issued client ID and the tokens are stored in
  `<data>/chatgpt/credentials.json`, created owner-only (0600) and written atomically. The host
  identifier is in `<data>/chatgpt/host-id`.
- **ID token.** Its RS256 signature is verified against OpenAI's published keys with
  `cryptography` (already in the dependency tree through pdfminer, now declared). Issuer,
  audience, expiry and nonce are checked too.
- **Refresh.** Tokens are refreshed under a lock two minutes before expiry. A terminal refresh
  error clears the tokens but keeps the registration. A network failure keeps them.
- **Sign-out.** It revokes the refresh token.
- **Exposure.** Tokens never reach the browser. Uvicorn's access log redacts the callback query,
  which carries the authorization code.

**Profiles.**

- **Two profiles.** *local* (the default) and *cloud* (the ChatGPT plan).
- **What the profile covers.** It applies to three roles: the interviewer, including topic
  planning; document analysis; and evaluation, which means CV review and interview reports.
  Each role routes every call to the model of the profile selected when the call starts.
- **Selecting cloud.** It requires a sign-in with plan usage and a confirmation that states what
  leaves the machine.
- **When the profile can change.** It changes, and a cloud sign-out returns it to local, only
  while no interview is connected and no job is queued or running.
- **A lost sign-in.** If the sign-in is lost while the cloud profile is selected, calls fail with
  "sign in again". They are not moved silently to the local models.
- **Storage.** The selection is stored in `execution-profile.json` in the data directory.
- **Data operations.** Backups, restores and "delete all my data" leave the selection and the
  ChatGPT credentials alone. The Settings page signs out explicitly.

**Models.** The default model for all roles is `gpt-6.1-terra`. It is configurable per role, and
so is the reasoning setting. The account must have access to the configured models.

**UI.** Settings follows OpenAI's UI guidelines:

- "Continue with ChatGPT" starts the sign-in;
- "Use your ChatGPT plan" explains plan usage;
- a "Using ChatGPT plan" notice and a "Manage usage" link to `https://chatgpt.com/settings/usage`
  are shown while the profile is active.

A hosted model is never warmed up: `ModelCapabilities.preload` is false, and the interview start
only checks that a valid token is available.

## Consequences

**What leaves the machine.** With the cloud profile, CVs, documents, transcripts and answers are
sent to OpenAI and count against the user's ChatGPT plan, including Plus's shared five-hour
limit. Audio never leaves the machine.

**Provenance.** Reports record `chatgpt:<model>`. Progress groups require the same model, so
cloud and local reports are never compared.

**Verification and availability.**

- The flow, refresh, revocation, adapter behaviour and UI are verified against scripted OAuth and
  Responses servers, and end to end with a fake account.
- The adapter assumes the documented `response.*` stream events. A live run needs the owner's
  sign-in. It must also confirm three things:
  - that dynamic registration is accepted for this app;
  - whether structured outputs and reasoning effort are accepted;
  - that the default model is available to the account.
- If OpenAI refuses the registration, the cloud profile stays unavailable until the app is
  admitted, for example through the interest form.

**Network.** The redirect works because the backend is published on `127.0.0.1` on the machine
that runs the browser. A remote deployment would need the documented credential-transfer
procedure.

**Follow-up.**

- Compare the profiles on the labelled transcript and the persona calibration set.
- Optionally list the account's models (`GET /v1/models`) in Settings.

## Alternatives considered

- **An OpenAI API key with Chat Completions** — implemented first, then replaced at the owner's
  request: it bills per token instead of using the subscription.
- **Reusing Codex CLI credentials** — not documented as allowed for other apps.
- **The official `openai` SDK** — one more dependency for one endpoint and a token that is not an
  API key.
- **Validating the ID token by TLS alone** (OIDC Core 3.1.3.7) — permitted for a direct token
  response, but OpenAI's guide asks for signature verification and the library was already
  present.
- **Falling back to the local models when the ChatGPT plan fails** — a silent change of model
  and of where data is processed. Errors are reported instead.
