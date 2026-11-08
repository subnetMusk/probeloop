"""Portable SQL rows plus owned blobs, recordings and logs, independent of database dialect."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import MetaData, Table, delete, func, insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.storage.database import (
    Base,
    current_revision,
    downgrade,
    migrate,
    revisions,
    sessionmaker,
)

OWNED_DIRS = ("sessions", "blobs", "logs")
MANAGED_DIRS = (*OWNED_DIRS, "exports")
FORMAT = "probeloop-data-v2"
# Backups written before the format recorded the schema revision.
LEGACY_FORMATS = {"probeloop-data-v1": "0003"}
MAX_JSON = 100 * 1024 * 1024
MAX_ARCHIVE = 20 * 1024 * 1024 * 1024


class SqlDataStore:
    """Backups record the schema revision they were taken at. A restore brings the empty database
    to that revision, inserts the rows, then applies the later migrations, so the migrations are
    the only definition of how older data is upgraded."""

    def __init__(self, engine: AsyncEngine, root: Path) -> None:
        self.engine = engine
        self.sessions = sessionmaker(engine)
        self.root = root.resolve()

    async def summary(self) -> dict[str, int]:
        async with self.sessions() as db:
            return {
                table.name: int(await db.scalar(select(func.count()).select_from(table)) or 0)
                for table in Base.metadata.sorted_tables
            }

    async def export_json(self) -> bytes:
        async with self.sessions() as db:
            tables = {
                table.name: [dict(row) for row in (await db.execute(select(table))).mappings()]
                for table in Base.metadata.sorted_tables
            }
        revision = await current_revision(self.engine)
        return json.dumps(
            {"format": FORMAT, "revision": revision, "tables": tables},
            ensure_ascii=False,
            indent=2,
            default=str,
        ).encode()

    async def backup(self) -> Path:
        data = await self.export_json()
        return await asyncio.to_thread(self._archive, data)

    def _owned(self, name: str) -> Path:
        directory = self.root / name
        if directory.is_symlink() or not directory.resolve().is_relative_to(self.root):
            raise ValueError("data directory must remain inside the configured root")
        return directory

    def _archive(self, data: bytes) -> Path:
        exports = self._owned("exports")
        exports.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix="backup-", suffix=".zip", dir=exports)
        os.close(descriptor)
        output = Path(name)
        try:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("data.json", data)
                archive.writestr(
                    "README.txt",
                    "ProbeLoop portable backup v1. Stop the backend and restore into an empty "
                    "database: probeloop restore-backup ARCHIVE. "
                    "Models, configuration and environment files are not included.\n",
                )
                for name in OWNED_DIRS:
                    directory = self._owned(name)
                    if directory.exists():
                        for file in directory.rglob("*"):
                            if file.is_symlink():
                                raise ValueError("symlinks are not supported in portable backups")
                            if file.is_file():
                                archive.write(file, file.relative_to(self.root).as_posix())
            return output
        except BaseException:
            output.unlink(missing_ok=True)
            raise

    async def delete_all(self) -> None:
        # Validate paths before changing either SQL or files.
        directories = [self._owned(name) for name in MANAGED_DIRS]
        async with self.sessions.begin() as db:
            for table in reversed(Base.metadata.sorted_tables):
                await db.execute(delete(table))
        await asyncio.to_thread(self._remove_directories, directories)

    def _remove_directories(self, directories: list[Path]) -> None:
        for directory in directories:
            if directory.exists():
                shutil.rmtree(directory)

    async def restore(self, archive: Path) -> None:
        if any((await self.summary()).values()):
            raise ValueError("restore requires an empty database")
        if await asyncio.to_thread(self._has_files):
            raise ValueError("restore requires empty data directories")
        with tempfile.TemporaryDirectory(prefix="probeloop-restore-") as staging:
            directory = Path(staging)
            revision, data = await asyncio.to_thread(self._unpack, archive, directory)
            known = revisions()
            if revision not in known:
                raise ValueError("backup from a newer or unknown version of ProbeLoop")
            head = known[-1]
            try:
                if revision != head:
                    await downgrade(self.engine, revision)
                tables = await self._tables()
                _check_rows(data, tables)
                async with self.engine.begin() as connection:
                    for table in tables.values():
                        rows = data[table.name]
                        if rows:
                            await connection.execute(insert(table), rows)
                if revision != head:
                    await migrate(self.engine)
                await asyncio.to_thread(self._copy_restored, directory)
            except BaseException:
                # The target was empty: return it to an empty database at the current schema, so
                # the restore can be retried.
                await self._reset()
                raise

    async def _tables(self) -> dict[str, Table]:
        """The application tables of the current schema, in dependency order."""

        def reflect(connection: Connection) -> dict[str, Table]:
            metadata = MetaData()
            metadata.reflect(bind=connection)
            return {
                table.name: table
                for table in metadata.sorted_tables
                if table.name != "alembic_version"
            }

        async with self.engine.connect() as connection:
            return await connection.run_sync(reflect)

    async def _reset(self) -> None:
        tables = await self._tables()
        async with self.engine.begin() as connection:
            for table in reversed(list(tables.values())):
                await connection.execute(delete(table))
        await migrate(self.engine)
        await asyncio.to_thread(
            self._remove_directories, [self._owned(name) for name in MANAGED_DIRS]
        )

    def _has_files(self) -> bool:
        return any(
            path.is_file() or path.is_symlink()
            for name in OWNED_DIRS
            for path in self._owned(name).rglob("*")
        )

    def _unpack(self, source: Path, staging: Path) -> tuple[str, dict[str, list[dict[str, Any]]]]:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)) or sum(e.file_size for e in entries) > MAX_ARCHIVE:
                raise ValueError("duplicate entries or oversized backup")
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in entry.filename
                    or path.as_posix() != entry.filename.rstrip("/")
                    or stat.S_ISLNK(entry.external_attr >> 16)
                ):
                    raise ValueError("unsafe backup path")
                if entry.filename in ("data.json", "README.txt"):
                    continue
                if not path.parts or path.parts[0] not in OWNED_DIRS:
                    raise ValueError("unknown backup content")
            if archive.getinfo("data.json").file_size > MAX_JSON:
                raise ValueError("oversized structured data")
            content = json.loads(archive.read("data.json"))
            if not isinstance(content, dict):
                raise ValueError("unknown backup format")
            if content.get("format") == FORMAT:
                revision = content.get("revision")
            else:
                revision = LEGACY_FORMATS.get(str(content.get("format")))
            if not isinstance(revision, str):
                raise ValueError("unknown backup format")
            tables = content.get("tables")
            if not isinstance(tables, dict) or any(
                not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
                for rows in tables.values()
            ):
                raise ValueError("invalid backup rows")
            for entry in entries:
                if PurePosixPath(entry.filename).parts[0] in OWNED_DIRS and not entry.is_dir():
                    destination = staging / entry.filename
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source_file, destination.open("wb") as target:
                        shutil.copyfileobj(source_file, target)
            return revision, tables

    def _copy_restored(self, staging: Path) -> None:
        for name in OWNED_DIRS:
            source = staging / name
            if source.exists():
                shutil.copytree(source, self._owned(name), dirs_exist_ok=True)


def _check_rows(data: dict[str, list[dict[str, Any]]], tables: dict[str, Table]) -> None:
    """The backup holds exactly the tables and columns of the schema it was taken at."""
    if set(data) != set(tables):
        raise ValueError("backup schema does not match its recorded version")
    for name, rows in data.items():
        columns = set(tables[name].columns.keys())
        if any(set(row) != columns for row in rows):
            raise ValueError("invalid backup rows")
