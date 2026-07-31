"""Runs an Evaluator over every item in a Dataset and records results on an EvalRun."""

from __future__ import annotations

import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.eval.evaluator import Evaluator
from app.metadata.models import DatasetItem, EvalRun


def run_eval(
    session: Session,
    eval_run: EvalRun,
    dataset_items: list[DatasetItem],
    evaluator: Evaluator,
    get_output: Callable[[DatasetItem], Any],
) -> EvalRun:
    """get_output produces the system output to score for a given item — the caller
    supplies this (e.g. replaying a stored trace's output, or invoking a live app)
    since Weft itself doesn't run the system under test."""
    item_results = []
    scores = []
    for item in dataset_items:
        output = get_output(item)
        result = evaluator.score({"input": item.input, "expected_output": item.expected_output}, output)
        scores.append(result.score)
        item_results.append(
            {
                "dataset_item_id": item.id,
                "score": result.score,
                "reasoning": result.reasoning,
            }
        )

    eval_run.status = "completed"
    eval_run.results = {
        "mean_score": sum(scores) / len(scores) if scores else 0.0,
        "item_count": len(scores),
        "items": item_results,
    }
    eval_run.completed_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(eval_run)
    session.commit()
    session.refresh(eval_run)
    return eval_run
