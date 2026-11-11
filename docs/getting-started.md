# Installation

## Packaged installation

Install and open Docker Desktop. Its Compose plugin, engine and CLI are sufficient; Python,
Node, Git and Make are not needed. Use Linux containers on Windows. Allocate enough CPU, memory
and disk to Docker Desktop for the selected speech models; the setup page reports the resources
visible to Docker, rather than assuming it can inspect the host's complete hardware.

Download the ZIP from [Releases](https://github.com/subnetMusk/probeloop/releases) and extract the
whole folder. Source code and release assets are public. Container images are distributed
publicly through GHCR, with amd64 and arm64 variants and immutable digests in
the ZIP's Compose file.

| System | Start |
|---|---|
| Windows | Double-click `Start.cmd` |
| macOS | Open `Start.command`; follow macOS security prompts for the downloaded script if required |
| Linux | Run `sh Start.sh` in the extracted directory |

The launcher checks Docker and Compose, starts the services and opens the browser after the
backend is healthy. Speech services may still be waiting for their models: that is expected on
an empty installation, and does not prevent the setup page from opening. Keep Docker Desktop
running while using ProbeLoop.

## Guided setup

1. **Connect tools.** ChatGPT is proposed for a fresh installation. Sign in and verify that the
   account allows the configured models. Local LLMs are optional; there is no automatic download
   of an Ollama model in the cloud path.
2. **Check resources and install models.** Install the live recogniser, Italian voice and Laya.
   The app shows their sizes, sources, licences and verification status. Downloads run in the
   background and reuse files that already match the expected checksums.
3. **Verify and complete.** Test the voice and review the per-role tool choices. Text interviews
   can be used after requested downloads finish while speech models are still loading. Voice interviews require working recognition
   and synthesis before they start.

You can return to this page from Settings. Installing Laya does not silently change the selected
reader: choose Laya explicitly for **Stated limits** after it is ready. It is not offered for
interview decisions or reports.

New installations leave **Second transcription with Whisper** off. Enabling it in Settings
downloads Whisper and enables the post-interview pass. Listening, manual transcript corrections
and revision history work without it. Existing installations retain the prior refinement setting.

## Model storage

Approximate download sizes, excluding container images:

| Component | Download | Required for |
|---|---|---|
| Parakeet int8 | 670 MB | Live speech recognition |
| Piper Serena | 64 MB | Italian speech synthesis |
| Fine-tuned Laya int8 and tokenizer | 342 MB | Local stated-limit reading |
| Whisper turbo | 1.62 GB additional | Optional second transcription |
| Ollama LLMs | Several GB each, depending on model | Only selected local language-model roles |

The installer checks free space in Docker's model volume before downloading and verifies sizes
and SHA-256 checksums before activation. Partial downloads are retained for retry; an interrupted
download is not an installed model. Model loading is a separate stage, reflected in availability.
Installation jobs resume after a backend restart. Do not delete named volumes to repair a download.

The provisional Laya release is hosted at
[submsk/probeloop-laya-stated-limits](https://huggingface.co/submsk/probeloop-laya-stated-limits).
The installed app pins an approved revision and hashes. Updating a fine-tuning on the Hub does
not automatically replace an existing model. An advanced URL setting can locate the same approved
files at another public HTTPS directory; files with different hashes are rejected.

## Optional Ollama

For cloud-only use, skip this section. For local LLMs:

1. Install [Ollama](https://ollama.com/download) natively on the host and start it.
2. In Settings, open **Ollama and Laya model address**. The default address for a native host
   installation is `http://host.docker.internal:11434`, as seen from the backend container.
3. Save and test the connection. If necessary, follow the
   [official server configuration instructions](https://docs.ollama.com/faq#how-do-i-configure-ollama-server)
   for Windows, macOS or Linux. Keep access scoped to the machine or trusted network.
4. Request installation of the model needed for a role. ProbeLoop uses Ollama's pull API and
   displays its progress; you do not need to run `ollama pull` manually.
5. Once the model is detected, select **Local LLM** for that role in Settings.

The native Ollama installer and any operating-system network configuration are user actions;
ProbeLoop does not install host software with administrator privileges. On macOS, the supported
speech containers use the CPU. Native Ollama can use the host's acceleration independently;
the cloud path needs no Ollama installation.

## Troubleshooting

- **Docker unavailable:** open Docker Desktop, wait for the engine, then run the launcher again.
- **Port occupied:** create `.env` beside the launchers containing `PROBELOOP_PORT=8001`, then
  start again. The launcher opens the chosen address; the bundle configures matching origins.
- **Installer unavailable:** start the complete Compose project, including `provisioner`.
- **Download interrupted:** retry the component in Settings. Valid completed files are reused.
- **Checksum error:** the file is not activated. Retry the pinned release; another fine-tuning
  needs its own reviewed manifest and app release.
- **Model installed but loading:** wait for its availability check. The interface stays usable.
- **Provider failed during an interview:** saved answers remain. Restore that provider and resume;
  the app does not substitute a different tool.

For source-based installation and checks, use [Development](development.md).
