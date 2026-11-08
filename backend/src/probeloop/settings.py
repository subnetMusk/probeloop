"""Runtime configuration, read from `PROBELOOP_*` environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROBELOOP_", env_file=None)

    data_dir: Path = Path("/data")
    # SQLite in the data volume by default; for PostgreSQL, e.g.
    # postgresql+asyncpg://probeloop:secret@postgres:5432/probeloop
    database_url: str | None = None
    log_level: str = "INFO"
    static_dir: Path | None = None  # the built SPA; the runtime image sets /app/static

    ollama_base_url: str = "http://host.docker.internal:11434"
    interviewer_model: str = "ministral-3:8b"
    context_window: int = 8192
    # Document analysis and job offer drafting: not latency-bound, so the larger model.
    analysis_model: str = "qwen3.5:9b"
    analysis_context_window: int = 8192
    evaluation_model: str = "qwen3.5:9b"
    evaluation_context_window: int = 16384
    # Thinking for the interview judging passes. "off" relies on the evidence-first schema; see
    # docs/research/evaluation-latency.md before enabling it.
    evaluation_judge_reasoning: Literal["off", "default"] = "off"
    keep_alive: str = "30m"

    # Cloud execution profile (docs/adr/0013-cloud-execution-profile.md): the interviewer,
    # document analysis and evaluation use the signed-in user's ChatGPT plan through Sign in with
    # ChatGPT. Speech recognition and synthesis always stay local.
    cloud_interviewer_model: str = "gpt-6.1-terra"
    cloud_analysis_model: str = "gpt-6.1-terra"
    cloud_evaluation_model: str = "gpt-6.1-terra"
    # The reasoning_effort sent when a request turns reasoning off: "none" where the models
    # support it, "low" where they do not, empty for models without reasoning control.
    cloud_reasoning_off: str | None = "none"
    cloud_context_window: int = 128_000
    llm_debug_log: bool = False
    llm_fake: bool = False  # scripted interviewer moves, for end-to-end tests

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

    @field_validator("cloud_reasoning_off", mode="before")
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def effective_database_url(self) -> str:
        return self.database_url or f"sqlite+aiosqlite:///{self.data_dir / 'probeloop.db'}"
