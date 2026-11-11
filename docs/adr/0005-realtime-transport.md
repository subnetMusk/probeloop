# 0005 — Realtime transport: own WebSocket protocol with explicit turn-taking

> **Decision record.** Current implementation guidance is in [architecture](../architecture.md) and [configuration](../configuration.md); later ADRs amend specific decisions.

- Status: Accepted
- Date: 2026-11-03

## Context

The interview loop is:

1. text-to-speech plays the question;
2. the candidate answers;
3. speech recognition shows a progressive transcript;
4. the candidate presses "end of answer";
5. the interviewer decides the next move.

The MVP deliberately avoids automatic interruption handling (barge-in). The audio has to reach
the server while the candidate is speaking.

## Decision

Use one WebSocket per live session, carrying typed JSON messages and binary audio frames.

- **Capture.** The browser captures audio with an AudioWorklet and sends 16 kHz mono PCM16 frames.
  The server discards frames outside the candidate's turn.
- **Playback.** Synthesised audio is streamed per sentence and scheduled on the `AudioContext`
  clock.
- **State.** The server holds the authoritative state.
- **Message metadata.** Control messages carry `client_msg_id` for idempotency, and server events
  carry `seq` for replay after a reconnection.
- **Everything else.** REST covers CRUD and jobs (status by polling).
- **Generated types.** TypeScript types are generated from OpenAPI and from the JSON Schema of the
  WebSocket messages.

## Consequences

- No server-side audio decoding and no ffmpeg dependency.
- The protocol and its edge cases (reconnection, cancellation, duplicate messages) must be
  implemented and tested by the project.
- Barge-in would require voice activity detection on the client and echo handling.

## Alternatives considered

- **WebRTC** — justified only for barge-in or echo cancellation.
- **Pipecat** (BSD-2) — its frame-pipeline model would shape the domain, and push-to-talk has open
  bugs. To be revisited if barge-in is added.
- **LiveKit Agents** — requires a LiveKit server.
- **FastRTC** — inactive.
- **Server-sent events plus a final upload** — prevents a progressive transcript.
