"""Read-side HTTP endpoints backed by app.storage.query."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.storage import query


def build_router(data_dir: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/traces")
    async def list_traces(limit: int = Query(default=50, ge=1, le=1000)) -> list[dict]:
        return query.list_traces(data_dir, limit=limit)

    @router.get("/traces/{trace_id}")
    async def get_trace(trace_id: str) -> list[dict]:
        spans = query.get_trace(data_dir, trace_id)
        if not spans:
            raise HTTPException(status_code=404, detail="trace not found")
        return spans

    return router
