"""Eval run HTTP endpoints per the plan: POST /eval-runs, GET /eval-runs/{id}.

Weft doesn't invoke the system under test itself (see app.eval.runner), so the
caller supplies the already-generated outputs to score, keyed by dataset_item_id.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.eval.evaluator import (
    Evaluator,
    ExactMatchEvaluator,
    RegexEvaluator,
    SchemaValidityEvaluator,
)
from app.eval.runner import run_eval
from app.metadata.models import Dataset, DatasetItem, EvalRun

router = APIRouter(prefix="/eval-runs")


class CreateEvalRunRequest(BaseModel):
    dataset_id: str
    evaluator_name: str
    evaluator_config: dict[str, Any] = {}
    outputs: dict[str, Any] = {}  # dataset_item_id -> output to score


def _build_evaluator(name: str, config: dict[str, Any]) -> Evaluator:
    if name == "exact_match":
        return ExactMatchEvaluator()
    if name == "regex":
        if "pattern" not in config:
            raise HTTPException(status_code=422, detail="regex evaluator requires evaluator_config.pattern")
        return RegexEvaluator(pattern=config["pattern"])
    if name == "schema_validity":
        if "required_keys" not in config:
            raise HTTPException(
                status_code=422, detail="schema_validity evaluator requires evaluator_config.required_keys"
            )
        return SchemaValidityEvaluator(required_keys=config["required_keys"])
    raise HTTPException(status_code=422, detail=f"unknown evaluator_name: {name!r}")


def _eval_run_out(run: EvalRun) -> dict:
    return {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "evaluator_name": run.evaluator_name,
        "status": run.status,
        "results": run.results,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.post("", status_code=201)
async def create_eval_run(
    body: CreateEvalRunRequest, session: Session = Depends(db_session)
) -> dict:
    dataset = session.get(Dataset, body.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")

    evaluator = _build_evaluator(body.evaluator_name, body.evaluator_config)

    items = session.execute(
        select(DatasetItem).where(DatasetItem.dataset_id == dataset.id)
    ).scalars().all()
    missing_outputs = [item.id for item in items if item.id not in body.outputs]
    if missing_outputs:
        raise HTTPException(
            status_code=422,
            detail=f"outputs missing for dataset_item_id(s): {missing_outputs}",
        )

    eval_run = EvalRun(dataset_id=dataset.id, evaluator_name=body.evaluator_name, status="running")
    session.add(eval_run)
    session.commit()
    session.refresh(eval_run)

    run_eval(
        session,
        eval_run,
        list(items),
        evaluator,
        get_output=lambda item: body.outputs[item.id],
    )
    return _eval_run_out(eval_run)


@router.get("/{eval_run_id}")
async def get_eval_run(eval_run_id: str, session: Session = Depends(db_session)) -> dict:
    run = session.get(EvalRun, eval_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="eval run not found")
    return _eval_run_out(run)
