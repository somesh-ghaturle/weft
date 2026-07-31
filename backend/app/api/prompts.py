"""Prompt CRUD/versioning HTTP endpoints per the plan:

GET/POST /prompts, POST /prompts/{id}/versions, POST /prompts/{id}/labels,
GET /prompts/{name}/labels/{label} (the SDK's get_prompt(name, label) hot path).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.metadata.models import Label, Prompt, PromptVersion

router = APIRouter(prefix="/prompts")


class CreatePromptRequest(BaseModel):
    name: str


class CreateVersionRequest(BaseModel):
    template: str
    config: dict[str, Any] = {}


class CreateLabelRequest(BaseModel):
    name: str
    version_id: str


def _prompt_out(prompt: Prompt) -> dict:
    return {"id": prompt.id, "name": prompt.name, "created_at": prompt.created_at.isoformat()}


def _version_out(version: PromptVersion) -> dict:
    return {
        "id": version.id,
        "prompt_id": version.prompt_id,
        "version_number": version.version_number,
        "template": version.template,
        "config": version.config,
        "created_at": version.created_at.isoformat(),
    }


def _label_out(label: Label) -> dict:
    return {
        "id": label.id,
        "prompt_id": label.prompt_id,
        "name": label.name,
        "version_id": label.version_id,
        "updated_at": label.updated_at.isoformat(),
    }


def _get_prompt_or_404(session: Session, prompt_id: str) -> Prompt:
    prompt = session.get(Prompt, prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    return prompt


@router.get("")
async def list_prompts(session: Session = Depends(db_session)) -> list[dict]:
    prompts = session.execute(select(Prompt)).scalars().all()
    return [_prompt_out(p) for p in prompts]


@router.post("", status_code=201)
async def create_prompt(body: CreatePromptRequest, session: Session = Depends(db_session)) -> dict:
    existing = session.execute(select(Prompt).where(Prompt.name == body.name)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="a prompt with this name already exists")
    prompt = Prompt(name=body.name)
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return _prompt_out(prompt)


@router.post("/{prompt_id}/versions", status_code=201)
async def create_version(
    prompt_id: str, body: CreateVersionRequest, session: Session = Depends(db_session)
) -> dict:
    prompt = _get_prompt_or_404(session, prompt_id)
    latest = session.execute(
        select(PromptVersion)
        .where(PromptVersion.prompt_id == prompt.id)
        .order_by(PromptVersion.version_number.desc())
    ).scalars().first()
    next_version_number = (latest.version_number + 1) if latest else 1

    version = PromptVersion(
        prompt_id=prompt.id,
        version_number=next_version_number,
        template=body.template,
        config=body.config,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return _version_out(version)


@router.post("/{prompt_id}/labels", status_code=201)
async def upsert_label(
    prompt_id: str, body: CreateLabelRequest, session: Session = Depends(db_session)
) -> dict:
    prompt = _get_prompt_or_404(session, prompt_id)
    version = session.get(PromptVersion, body.version_id)
    if version is None or version.prompt_id != prompt.id:
        raise HTTPException(status_code=404, detail="prompt version not found")

    label = session.execute(
        select(Label).where(Label.prompt_id == prompt.id, Label.name == body.name)
    ).scalar_one_or_none()
    if label is None:
        label = Label(prompt_id=prompt.id, name=body.name, version_id=version.id)
        session.add(label)
    else:
        label.version_id = version.id  # atomic reassignment: single UPDATE on commit
    session.commit()
    session.refresh(label)
    return _label_out(label)


@router.get("/{name}/labels/{label}")
async def resolve_label(name: str, label: str, session: Session = Depends(db_session)) -> dict:
    prompt = session.execute(select(Prompt).where(Prompt.name == name)).scalar_one_or_none()
    if prompt is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    label_row = session.execute(
        select(Label).where(Label.prompt_id == prompt.id, Label.name == label)
    ).scalar_one_or_none()
    if label_row is None:
        raise HTTPException(status_code=404, detail="label not found")
    return _version_out(label_row.version)
