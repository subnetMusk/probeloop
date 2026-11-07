"""Runtime configuration, read from `PROBELOOP_*` environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROBELOOP_", env_file=None)

    data_dir: Path = Path("/data")
    log_level: str = "INFO"
    static_dir: Path | None = None  # the built SPA; the runtime image sets /app/static

    ollama_base_url: str = "http://host.docker.internal:11434"
    interviewer_model: str = "ministral-3:8b"
    context_window: int = 8192
    keep_alive: str = "30m"
    llm_debug_log: bool = False

    # Speech services (Compose: stt-worker and tts-piper). Without both, voice interviews are off.
    stt_url: str | None = None
    tts_url: str | None = None
    tts_voice_it: str | None = "it_IT-serena-medium"
    tts_voice_en: str | None = None  # no English voice is chosen yet
    speech_fake: bool = False  # fake recogniser and synthesiser, for end-to-end tests
    answer_warning_s: float = 240.0
    answer_limit_s: float = 360.0

    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    allowed_origins: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
