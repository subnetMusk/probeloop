"""Download portable user data and explicitly delete the application's stored content."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from starlette.background import BackgroundTask

from probeloop.workspace.service import DataBusyError, DataService


class DeleteAllRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: Literal["DELETE ALL DATA"]


class BackupReady(BaseModel):
    id: str


def data_router(data: DataService) -> APIRouter:
    router = APIRouter(prefix="/api/data")

    @router.get("/summary")
    async def summary() -> dict[str, int]:
        return await data.store.summary()

    @router.get("/export")
    async def export_json() -> Response:
        try:
            content = await data.export_json()
        except DataBusyError as exc:
            raise HTTPException(409, str(exc)) from exc
        return Response(
            content,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="probeloop-data.json"'},
        )

    @router.post("/backup")
    async def prepare_backup() -> BackupReady:
        try:
            return BackupReady(id=await data.prepare_backup())
        except DataBusyError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/backup/{token}")
    async def backup(token: str) -> FileResponse:
        try:
            archive = data.take_backup(token)
        except KeyError as exc:
            raise HTTPException(404, "backup no longer available") from exc
        return FileResponse(
            archive,
            media_type="application/zip",
            filename="probeloop-backup.zip",
            background=BackgroundTask(archive.unlink, missing_ok=True),
        )

    @router.post("/delete-all", status_code=204)
    async def delete_all(body: DeleteAllRequest) -> Response:
        try:
            await data.delete_all()
        except DataBusyError as exc:
            raise HTTPException(409, str(exc)) from exc
        return Response(status_code=204)

    return router
