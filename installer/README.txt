ProbeLoop · first installation

1. Install and open Docker Desktop. Wait until its engine is running.
2. Extract this entire ZIP into a folder you want to keep.
3. Start the launcher:
   Windows: double-click Start.cmd.
   macOS: open Start.command (if required, allow it in system security settings).
   Linux: run sh Start.sh from this folder.
4. The browser opens ProbeLoop. Follow the guided setup to connect ChatGPT and
   download the speech components. Ollama and local language models are optional.

Keep Docker Desktop running while using the application. No Python, Node, Git or
Make installation is needed. Internet access is needed for the initial image and
model downloads and for ChatGPT; installed speech components run locally.

Whisper's second transcription is optional and initially off. You can always
listen to recordings and correct their transcripts manually.

To start again, use the same launcher or start the probeloop project in Docker
Desktop, then open http://127.0.0.1:8000. Stop the project in Docker Desktop to
release resources. Stopping or replacing containers preserves the named volumes.
Do not delete the probeloop_data or probeloop_models volumes to update the app.

Updates: download a newer package, stop the old project, and start the new package.
Create a backup from Settings first. Keep your .env file if you changed the port.

Port already occupied? Create .env beside the launchers with this line:
PROBELOOP_PORT=8001
Start again. The launcher opens the configured address automatically.

The ZIP contains fixed image digests. It never installs host services or grants
the application access to Docker's socket. Container images contain application
code and dependencies, but no model weights, recordings, credentials or user data.

This is an early-development release. Hardware-specific speech performance and
interview quality remain under evaluation. See the project documentation.
