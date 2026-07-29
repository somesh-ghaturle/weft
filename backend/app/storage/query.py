"""Read-side query layer: DuckDB queries directly against the Parquet directory.

Read and write paths never share a DuckDB connection/writer lock; DuckDB opens
the Parquet files fresh (read-only glob) per query, so ingestion (writer.py)
and querying here never contend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


def _glob(data_dir: Path) -> str:
    return str(data_dir / "*.parquet")


def list_traces(data_dir: Path, limit: int = 50) -> list[dict[str, Any]]:
    glob_path = _glob(data_dir)
    if not any(data_dir.glob("*.parquet")):
        return []
    con = duckdb.connect(database=":memory:")
    rows = con.execute(
        f"""
        SELECT
            trace_id,
            count(*) AS span_count,
            min(start_time_unix_nano) AS trace_start_ns,
            max(end_time_unix_nano) AS trace_end_ns,
            sum(duration_ms) AS total_duration_ms,
            sum(gen_ai_usage_input_tokens) AS total_input_tokens,
            sum(gen_ai_usage_output_tokens) AS total_output_tokens,
            list(DISTINCT gen_ai_request_model) AS models
        FROM read_parquet('{glob_path}')
        GROUP BY trace_id
        ORDER BY trace_start_ns DESC
        LIMIT {int(limit)}
        """
    ).fetchall()
    columns = [d[0] for d in con.description]
    return [dict(zip(columns, row)) for row in rows]


def get_trace(data_dir: Path, trace_id: str) -> list[dict[str, Any]]:
    glob_path = _glob(data_dir)
    if not any(data_dir.glob("*.parquet")):
        return []
    con = duckdb.connect(database=":memory:")
    rows = con.execute(
        f"""
        SELECT *
        FROM read_parquet('{glob_path}')
        WHERE trace_id = ?
        ORDER BY start_time_unix_nano ASC
        """,
        [trace_id],
    ).fetchall()
    columns = [d[0] for d in con.description]
    return [dict(zip(columns, row)) for row in rows]
