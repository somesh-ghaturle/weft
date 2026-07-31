"""Dataset CRUD HTTP endpoints per the plan: GET/POST /datasets, POST /datasets/{id}/items
(incl. promote-trace-to-item)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.metadata.models import Dataset, DatasetItem
from app.storage import query as trace_query


class CreateDatasetRequest(BaseModel):
    name: str
    description: str = ""


class CreateItemRequest(BaseModel):
    input: dict[str, Any] | None = None
    expected_output: dict[str, Any] | None = None
    source_trace_id: str | None = None


def _dataset_out(dataset: Dataset) -> dict:
    return {
        "id": dataset.id,
        "name": dataset.name,
        "description": dataset.description,
        "created_at": dataset.created_at.isoformat(),
    }


def _item_out(item: DatasetItem) -> dict:
    return {
        "id": item.id,
        "dataset_id": item.dataset_id,
        "input": item.input,
        "expected_output": item.expected_output,
        "source_trace_id": item.source_trace_id,
        "created_at": item.created_at.isoformat(),
    }


def _get_dataset_or_404(session: Session, dataset_id: str) -> Dataset:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return dataset


def build_router(data_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/datasets")

    @router.get("")
    async def list_datasets(session: Session = Depends(db_session)) -> list[dict]:
        datasets = session.execute(select(Dataset)).scalars().all()
        return [_dataset_out(d) for d in datasets]

    @router.post("", status_code=201)
    async def create_dataset(
        body: CreateDatasetRequest, session: Session = Depends(db_session)
    ) -> dict:
        existing = session.execute(
            select(Dataset).where(Dataset.name == body.name)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail="a dataset with this name already exists")
        dataset = Dataset(name=body.name, description=body.description)
        session.add(dataset)
        session.commit()
        session.refresh(dataset)
        return _dataset_out(dataset)

    @router.post("/{dataset_id}/items", status_code=201)
    async def create_item(
        dataset_id: str, body: CreateItemRequest, session: Session = Depends(db_session)
    ) -> dict:
        dataset = _get_dataset_or_404(session, dataset_id)

        item_input = body.input
        expected_output = body.expected_output

        if body.source_trace_id is not None:
            spans = trace_query.get_trace(data_dir, body.source_trace_id)
            if not spans:
                raise HTTPException(status_code=404, detail="source trace not found")
            if item_input is None:
                root = min(spans, key=lambda s: s["start_time_unix_nano"])
                item_input = {
                    "trace_id": body.source_trace_id,
                    "root_span_name": root["name"],
                    "gen_ai_request_model": root["gen_ai_request_model"],
                }

        if item_input is None:
            raise HTTPException(
                status_code=422, detail="one of input or source_trace_id must be provided"
            )

        item = DatasetItem(
            dataset_id=dataset.id,
            input=item_input,
            expected_output=expected_output,
            source_trace_id=body.source_trace_id,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return _item_out(item)

    return router
