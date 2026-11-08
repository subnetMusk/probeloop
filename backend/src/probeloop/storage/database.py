"""Database engine, ORM tables and migrations (ADR 0004).

The ORM rows are not domain objects: the stores map between the two explicitly. SQLite is the
default (WAL, foreign keys on); PostgreSQL is supported through the same tables, and the
contract tests run on both.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    event,
)
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MIGRATIONS = Path(__file__).parent / "migrations"


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[Any]: JSON}


class SessionRow(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))
    phase: Mapped[str | None] = mapped_column(String(32))
    interview_type: Mapped[str] = mapped_column(String(16))
    difficulty: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(8))
    modality: Mapped[str] = mapped_column(String(8))
    target_duration_s: Mapped[int]
    custom_instructions: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, Any]]
    coverage: Mapped[dict[str, Any]]
    started_at: Mapped[float | None] = mapped_column(Float)
    ended_at: Mapped[float | None] = mapped_column(Float)
    end_reason: Mapped[str | None] = mapped_column(String(16))
    failure: Mapped[str | None] = mapped_column(Text)
    paused_at: Mapped[float | None] = mapped_column(Float)
    paused_total_s: Mapped[float] = mapped_column(Float)
    paused_phase: Mapped[str | None] = mapped_column(String(32))
    final_question_asked: Mapped[bool]
    snapshot_id: Mapped[str | None] = mapped_column(String(32))

    turns: Mapped[list[TurnRow]] = relationship(
        order_by="TurnRow.seq", cascade="all, delete-orphan", passive_deletes=True
    )


class TurnRow(Base):
    __tablename__ = "turns"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(primary_key=True)
    speaker: Mapped[str] = mapped_column(String(16))
    at: Mapped[float] = mapped_column(Float)
    elapsed_s: Mapped[float] = mapped_column(Float)
    move: Mapped[dict[str, Any] | None]

    revisions: Mapped[list[RevisionRow]] = relationship(
        order_by="RevisionRow.number", cascade="all, delete-orphan", passive_deletes=True
    )


class RevisionRow(Base):
    __tablename__ = "transcript_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "turn_seq"], ["turns.session_id", "turns.seq"], ondelete="CASCADE"
        ),
    )

    session_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    turn_seq: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[float] = mapped_column(Float)
    engine_ref: Mapped[str | None] = mapped_column(String(200))
    words: Mapped[list[Any]]


class TurnMetricsRow(Base):
    __tablename__ = "turn_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    record: Mapped[dict[str, Any]]


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(100))
    filename: Mapped[str | None] = mapped_column(String(255))
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    warnings: Mapped[list[Any]]
    created_at: Mapped[float] = mapped_column(Float)


class ContextExtractionRow(Base):
    __tablename__ = "context_extractions"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict[str, Any]]


class ProfileRow(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)

    resources: Mapped[list[ProfileResourceRow]] = relationship(
        order_by="ProfileResourceRow.position", cascade="all, delete-orphan", passive_deletes=True
    )


class ProfileResourceRow(Base):
    __tablename__ = "profile_resources"

    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))


class PreparationRow(Base):
    __tablename__ = "preparations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[float] = mapped_column(Float)
    language: Mapped[str] = mapped_column(String(8))
    job_mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    document_ids: Mapped[list[Any]]
    facts: Mapped[list[Any]]
    matches: Mapped[list[Any]]
    area: Mapped[dict[str, Any] | None]
    vocabulary: Mapped[list[Any]]
    error: Mapped[str | None] = mapped_column(Text)
    profile_id: Mapped[str | None] = mapped_column(String(32))
    snapshot_id: Mapped[str | None] = mapped_column(String(32))


class SnapshotRow(Base):
    __tablename__ = "context_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    preparation_id: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[float] = mapped_column(Float)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    data: Mapped[dict[str, Any]]


class JobRow(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_subject", "subject_id", "kind"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), index=True)
    progress: Mapped[float] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]]
    result: Mapped[dict[str, Any] | None]
    created_at: Mapped[float] = mapped_column(Float)
    started_at: Mapped[float | None] = mapped_column(Float)
    finished_at: Mapped[float | None] = mapped_column(Float)


class ReportRow(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_subject_version", "kind", "subject_id", "version", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    subject_id: Mapped[str] = mapped_column(String(32))
    version: Mapped[int]
    created_at: Mapped[float] = mapped_column(Float)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("context_snapshots.id"))
    data: Mapped[dict[str, Any]]


def create_engine(url: str) -> AsyncEngine:
    engine = create_async_engine(url)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(connection: Any, _: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[Any]:
    return async_sessionmaker(engine, expire_on_commit=False)


def alembic_config(connection: Connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.attributes["connection"] = connection
    return config


async def migrate(engine: AsyncEngine, revision: str = "head") -> None:
    """Bring the schema to `revision`. Runs at startup: there is one user and one process."""

    def upgrade(connection: Connection) -> None:
        command.upgrade(alembic_config(connection), revision)

    async with engine.begin() as connection:
        await connection.run_sync(upgrade)


async def downgrade(engine: AsyncEngine, revision: str) -> None:
    def run(connection: Connection) -> None:
        command.downgrade(alembic_config(connection), revision)

    async with engine.begin() as connection:
        await connection.run_sync(run)
