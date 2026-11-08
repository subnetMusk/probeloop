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

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from probeloop.storage.database import Base

OWNED_DIRS = ("sessions", "blobs", "logs")
MANAGED_DIRS = (*OWNED_DIRS, "exports")
FORMAT = "probeloop-data-v1"
MAX_JSON = 100 * 1024 * 1024
MAX_ARCHIVE = 20 * 1024 * 1024 * 1024


class SqlDataStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], root: Path) -> None:
        self.sessions = sessions
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
        return json.dumps(
            {"format": FORMAT, "tables": tables}, ensure_ascii=False, indent=2
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
            data = await asyncio.to_thread(self._unpack, archive, directory)
            async with self.sessions.begin() as db:
                for table in Base.metadata.sorted_tables:
                    rows = data[table.name]
                    if rows:
                        await db.execute(insert(table), rows)
            try:
                await asyncio.to_thread(self._copy_restored, directory)
            except BaseException:
                # The target was empty: remove this incomplete restore so it can be retried.
                await self.delete_all()
                raise

    def _has_files(self) -> bool:
        return any(
            path.is_file() or path.is_symlink()
            for name in OWNED_DIRS
            for path in self._owned(name).rglob("*")
        )

    def _unpack(self, source: Path, staging: Path) -> dict[str, list[dict[str, Any]]]:
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
            if not isinstance(content, dict) or content.get("format") != FORMAT:
                raise ValueError("unknown backup format")
            tables = content.get("tables")
            expected = {t.name: t for t in Base.metadata.sorted_tables}
            if not isinstance(tables, dict) or set(tables) != set(expected):
                raise ValueError("backup schema does not match this application version")
            for name, rows in tables.items():
                columns = set(expected[name].columns.keys())
                if not isinstance(rows, list) or any(
                    not isinstance(row, dict) or set(row) != columns for row in rows
                ):
                    raise ValueError("invalid backup rows")
            for entry in entries:
                if PurePosixPath(entry.filename).parts[0] in OWNED_DIRS and not entry.is_dir():
                    destination = staging / entry.filename
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source_file, destination.open("wb") as target:
                        shutil.copyfileobj(source_file, target)
            return tables

    def _copy_restored(self, staging: Path) -> None:
        for name in OWNED_DIRS:
            source = staging / name
            if source.exists():
                shutil.copytree(source, self._owned(name), dirs_exist_ok=True)
