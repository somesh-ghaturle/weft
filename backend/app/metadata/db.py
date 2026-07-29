"""Engine/session setup for the relational metadata store.

Defaults to a local SQLite file (plan's stated "acceptable for local dev only"
fallback). Set WEFT_METADATA_DATABASE_URL to a Postgres DSN to switch — the
SQLAlchemy models in app.metadata.models are portable across both.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.metadata.models import Base

DEFAULT_SQLITE_PATH = os.environ.get("WEFT_DATA_DIR", "./data") + "/metadata.db"
DATABASE_URL = os.environ.get(
    "WEFT_METADATA_DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}"
)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()
