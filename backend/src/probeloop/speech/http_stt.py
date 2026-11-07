"""SpeechToText over HTTP: the backend's client of the stt-worker (see `probeloop.speech.wire`)."""

from __future__ import annotations

import httpx
from pydantic import ValidationError

from probeloop.speech.audio import SAMPLE_RATE, PcmAudio
from probeloop.speech.ports import ServiceStatus, SpeechError, TranscribeOptions, Transcription
from probeloop.speech.wire import Engine, TranscriptionBody


class HttpSpeechToText:
    """One engine of the worker. `engine_ref` reports the worker's engine after the first call."""

    def __init__(
        self,
        base_url: str,
        *,
        engine: Engine = "live",
        timeout_s: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._engine = engine
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_s)
        self._engine_ref = f"stt-worker/{engine}"

    @property
    def engine_ref(self) -> str:
        return self._engine_ref

    async def transcribe(self, audio: PcmAudio, options: TranscribeOptions) -> Transcription:
        if audio.sample_rate != SAMPLE_RATE:
            raise SpeechError("the stt-worker accepts 16 kHz audio only")
        params: dict[str, str] = {
            "engine": self._engine,
            "language": options.language,
            "word_timestamps": "true" if options.word_timestamps else "false",
            "sample_rate": str(audio.sample_rate),
        }
        if options.initial_prompt:
            params["initial_prompt"] = options.initial_prompt
        try:
            response = await self._client.post(
                "/transcribe",
                params=params,
                content=audio.data,
                headers={"Content-Type": "application/octet-stream"},
            )
        except httpx.HTTPError as exc:
            raise SpeechError(f"stt-worker unreachable: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise SpeechError(f"stt-worker answered {response.status_code}")
        try:
            body = TranscriptionBody.model_validate_json(response.content)
        except ValidationError as exc:
            raise SpeechError("stt-worker sent an invalid response") from exc
        self._engine_ref = body.engine_ref
        return body.to_transcription()

    async def status(self) -> ServiceStatus:
        """Whether the worker can transcribe now. An unreachable worker may still be starting."""
        try:
            response = await self._client.get("/health", timeout=5.0)
        except httpx.HTTPError:
            return ServiceStatus("starting", "the speech recognition service is unreachable")
        if response.status_code == 200:
            return ServiceStatus("ready")
        try:
            state = response.json().get("status")
        except (ValueError, AttributeError):
            state = None
        if state == "loading":
            return ServiceStatus(
                "starting", "the speech recognition service is still loading its model"
            )
        return ServiceStatus(
            "failed", "the speech recognition service is not working (see its logs)"
        )

    async def aclose(self) -> None:
        await self._client.aclose()
