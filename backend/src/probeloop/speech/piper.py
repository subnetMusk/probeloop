"""TextToSpeech through Piper's HTTP server (the `tts-piper` service, ADR 0010).

Piper is GPL software, so it never runs in this process: the backend only sends it text and
receives WAV audio. Its server answers `POST /synthesize` with the whole sentence at once.
"""

from __future__ import annotations

import httpx

from probeloop.speech.audio import PcmAudio, from_wav
from probeloop.speech.ports import ServiceStatus, SpeechError


class PiperTextToSpeech:
    def __init__(
        self, base_url: str, *, timeout_s: float = 30.0, client: httpx.AsyncClient | None = None
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_s)

    async def synthesize(self, text: str, voice: str) -> PcmAudio:
        if not text.strip():
            raise SpeechError("nothing to synthesise")
        try:
            response = await self._client.post("/synthesize", json={"text": text, "voice": voice})
        except httpx.HTTPError as exc:
            raise SpeechError(f"tts-piper unreachable: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise SpeechError(f"tts-piper answered {response.status_code}")
        try:
            audio = from_wav(response.content)
        except ValueError as exc:
            raise SpeechError("tts-piper sent invalid audio") from exc
        if not audio.data:
            raise SpeechError("tts-piper sent no audio")
        return audio

    async def status(self, voice: str) -> ServiceStatus:
        """Whether `voice` can be used now. An unreachable service may still be starting."""
        try:
            response = await self._client.get("/voices", timeout=5.0)
        except httpx.HTTPError:
            return ServiceStatus("starting", "the speech synthesis service is unreachable")
        if response.status_code != 200:
            return ServiceStatus(
                "failed", f"the speech synthesis service answered {response.status_code}"
            )
        try:
            voices = response.json()
        except ValueError:
            return ServiceStatus("failed", "the speech synthesis service sent an invalid answer")
        if not isinstance(voices, dict) or voice not in voices:
            return ServiceStatus(
                "failed", f"the voice '{voice}' is not installed in the speech synthesis service"
            )
        return ServiceStatus("ready")

    async def aclose(self) -> None:
        await self._client.aclose()
