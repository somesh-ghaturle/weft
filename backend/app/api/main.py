"""App entrypoint: wires the span writer, OTLP ingestion, and query routes together."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.traces import build_router as build_traces_router
from app.ingestion.otlp import build_router as build_otlp_router
from app.metadata.db import init_db
from app.storage.writer import SpanWriter

DATA_DIR = Path(os.environ.get("WEFT_DATA_DIR", "./data")).resolve()

writer = SpanWriter(DATA_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    writer.start()
    try:
        yield
    finally:
        writer.stop()


app = FastAPI(title="weft", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(build_otlp_router(writer))
app.include_router(build_traces_router(DATA_DIR))
