"""stt-worker: speech recognition as an internal HTTP service.

This is the second entrypoint of the package (`python -m probeloop.speech.worker`). It hosts the
recognisers in-process and serves them to the backend over the internal Compose network; the API
is described in `probeloop.speech.wire`.

Requests run one at a time. Each engine already uses several threads, and the CPU is shared with
the backend, Piper and the browser.

`python -m probeloop.speech.worker download` fills the Hugging Face cache instead of serving.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Literal, Protocol, runtime_checkable

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings, SettingsConfigDict

from probeloop import logging_setup
from probeloop.speech.audio import SAMPLE_RATE, SAMPLE_WIDTH, PcmAudio
from probeloop.speech.ports import SpeechError, SpeechToText, TranscribeOptions
from probeloop.speech.wire import (
    MAX_AUDIO_S,
    MAX_PROMPT_CHARS,
    Engine,
    HealthBody,
    TranscriptionBody,
)

if TYPE_CHECKING:
    from probeloop.speech.parakeet import ParakeetSpeechToText
    from probeloop.speech.whisper import WhisperSpeechToText

logger = logging.getLogger("probeloop.speech.worker")  # also when run as __main__

MAX_BODY_BYTES = MAX_AUDIO_S * SAMPLE_RATE * SAMPLE_WIDTH
WARM_UP = PcmAudio(bytes(SAMPLE_RATE * SAMPLE_WIDTH // 2))  # half a second of silence


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROBELOOP_STT_", env_file=None)

    host: str = "0.0.0.0"  # noqa: S104 - the container is reachable only on the internal network
    port: int = 8000
    log_level: str = "INFO"
    threads: int = 6
    live_model: str = "nemo-parakeet-tdt-0.6b-v3"
    live_quantization: str | None = "int8"
    refine_model: str = "large-v3-turbo"
    refine_compute_type: str = "int8"
    refine_beam_size: int = 1
    preload_refine: bool = False
    # Whisper takes about 1 GB. It is used after an interview, so it is released once idle
    # instead of staying in memory during the next one. 0 keeps it loaded.
    refine_idle_unload_s: float = 120.0


@runtime_checkable
class Unloadable(Protocol):
    @property
    def loaded(self) -> bool: ...

    def unload(self) -> None: ...


def create_worker_app(
    engines: Mapping[Engine, SpeechToText],
    *,
    preload: Sequence[Engine] = (),
    idle_unload_s: Mapping[Engine, float] | None = None,
    idle_check_s: float = 10.0,
) -> FastAPI:
    """Serve `engines`. The engines in `preload` are loaded at startup; until then the worker
    is not healthy, so Compose and the backend can tell a loading worker from a ready one.

    An engine listed in `idle_unload_s` is unloaded once it has not been used for that long; the
    next request loads it again.
    """
    state: dict[str, Literal["loading", "ready", "failed"]] = {
        "status": "loading" if preload else "ready"
    }
    lock = asyncio.Lock()
    last_used: dict[Engine, float] = {}
    unload_after = {k: v for k, v in (idle_unload_s or {}).items() if v > 0}

    async def warm_up() -> None:
        for name in preload:
            started = time.perf_counter()
            try:
                async with lock:
                    await engines[name].transcribe(WARM_UP, TranscribeOptions(language="it"))
            except SpeechError:
                logger.exception("speech engine failed to load", extra={"engine": name})
                state["status"] = "failed"
                return
            logger.info(
                "speech engine ready",
                extra={
                    "engine": name,
                    "engine_ref": engines[name].engine_ref,
                    "load_s": round(time.perf_counter() - started, 1),
                },
            )
        state["status"] = "ready"

    async def unload_idle() -> None:
        while True:
            await asyncio.sleep(idle_check_s)
            for name, after_s in unload_after.items():
                engine = engines.get(name)
                used = last_used.get(name)
                if not isinstance(engine, Unloadable) or used is None:
                    continue
                if engine.loaded and time.monotonic() - used >= after_s:
                    async with lock:
                        await asyncio.to_thread(engine.unload)
                    logger.info("idle speech engine unloaded", extra={"engine": name})

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        tasks = []
        if preload:
            tasks.append(asyncio.create_task(warm_up()))
        if unload_after:
            tasks.append(asyncio.create_task(unload_idle()))
        yield
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="ProbeLoop stt-worker", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> JSONResponse:
        body = HealthBody(
            status=state["status"], engines={k: v.engine_ref for k, v in engines.items()}
        )
        code = 200 if state["status"] == "ready" else 503
        return JSONResponse(body.model_dump(), status_code=code)

    @app.post("/transcribe")
    async def transcribe(
        request: Request,
        language: Annotated[str, Query(pattern=r"^[a-z]{2,3}$")],
        engine: Engine = "live",
        initial_prompt: Annotated[str | None, Query(max_length=MAX_PROMPT_CHARS)] = None,
        word_timestamps: bool = False,
        sample_rate: int = SAMPLE_RATE,
    ) -> TranscriptionBody:
        recogniser = engines.get(engine)
        if recogniser is None:
            raise HTTPException(status_code=404, detail="engine not available")
        if engine in preload and state["status"] != "ready":
            raise HTTPException(status_code=503, detail="engine not ready")
        content_type = request.headers.get("content-type", "").split(";")[0].strip()
        if content_type != "application/octet-stream":
            raise HTTPException(status_code=415, detail="send raw PCM as application/octet-stream")
        if sample_rate != SAMPLE_RATE:
            raise HTTPException(status_code=422, detail="only 16 kHz audio is accepted")
        audio = PcmAudio(await _read_pcm(request))
        options = TranscribeOptions(
            language=language, initial_prompt=initial_prompt, word_timestamps=word_timestamps
        )
        async with lock:
            started = time.perf_counter()
            try:
                result = await recogniser.transcribe(audio, options)
            except SpeechError as exc:
                logger.warning("transcription failed", extra={"engine": engine, "error": str(exc)})
                raise HTTPException(status_code=503, detail="speech recognition failed") from exc
            elapsed = time.perf_counter() - started
            last_used[engine] = time.monotonic()
        logger.info(
            "audio transcribed",
            extra={
                "engine": engine,
                "audio_s": round(audio.duration_s, 2),
                "processing_s": round(elapsed, 3),
            },
        )
        return TranscriptionBody.of(result, elapsed)

    return app


async def _read_pcm(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="audio too long")
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="audio too long")
    if len(body) % SAMPLE_WIDTH:
        raise HTTPException(status_code=400, detail="16-bit PCM needs an even number of bytes")
    return bytes(body)


def build_engines(
    settings: WorkerSettings,
) -> dict[Engine, ParakeetSpeechToText | WhisperSpeechToText]:
    # Imported here so that the app factory works without the `stt` extra (tests use fakes).
    from probeloop.speech.parakeet import ParakeetSpeechToText
    from probeloop.speech.whisper import WhisperSpeechToText

    return {
        "live": ParakeetSpeechToText(
            model=settings.live_model,
            quantization=settings.live_quantization,
            threads=settings.threads,
        ),
        "refine": WhisperSpeechToText(
            model=settings.refine_model,
            compute_type=settings.refine_compute_type,
            threads=settings.threads,
            beam_size=settings.refine_beam_size,
        ),
    }


def download(settings: WorkerSettings) -> None:
    """Load both engines once, which downloads their models into the Hugging Face cache."""
    for name, engine in build_engines(settings).items():
        logger.info("downloading speech model", extra={"engine": name})
        engine.load()
        logger.info("speech model available", extra={"engine_ref": engine.engine_ref})


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="probeloop.speech.worker")
    parser.add_argument("command", nargs="?", choices=["serve", "download"], default="serve")
    args = parser.parse_args(argv)
    settings = WorkerSettings()
    logging_setup.configure(settings.log_level)
    if args.command == "download":
        download(settings)
        return
    preload: list[Engine] = ["live", "refine"] if settings.preload_refine else ["live"]
    app = create_worker_app(
        build_engines(settings),
        preload=preload,
        idle_unload_s={"refine": settings.refine_idle_unload_s},
    )
    # No access log: query strings carry the vocabulary prompt, which may come from the CV.
    uvicorn.run(app, host=settings.host, port=settings.port, access_log=False, log_config=None)


if __name__ == "__main__":
    main()
