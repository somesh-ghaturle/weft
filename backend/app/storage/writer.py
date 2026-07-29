"""Single background writer that batches spans and flushes them to Parquet.

DuckDB is a poor concurrent writer, so all ingestion paths must go through this
one writer instead of opening their own DuckDB connections. Producers call
enqueue(); a single background thread owns the batching and file writes.
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

SPAN_SCHEMA = pa.schema(
    [
        ("trace_id", pa.string()),
        ("span_id", pa.string()),
        ("parent_span_id", pa.string()),
        ("name", pa.string()),
        ("kind", pa.string()),
        ("start_time_unix_nano", pa.int64()),
        ("end_time_unix_nano", pa.int64()),
        ("duration_ms", pa.float64()),
        ("status_code", pa.string()),
        ("service_name", pa.string()),
        ("gen_ai_system", pa.string()),
        ("gen_ai_request_model", pa.string()),
        ("gen_ai_usage_input_tokens", pa.int64()),
        ("gen_ai_usage_output_tokens", pa.int64()),
        ("attributes_json", pa.string()),
    ]
)


class SpanWriter:
    """Owns the only DuckDB/Parquet write path in the process."""

    def __init__(self, data_dir: Path, flush_interval_seconds: float = 2.0, flush_batch_size: int = 500):
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._flush_interval = flush_interval_seconds
        self._flush_batch_size = flush_batch_size
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="weft-span-writer")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=10)

    def enqueue(self, span_row: dict[str, Any]) -> None:
        self._queue.put(span_row)

    def _run(self) -> None:
        batch: list[dict[str, Any]] = []
        last_flush = time.monotonic()
        while not self._stop_event.is_set():
            timeout = max(0.0, self._flush_interval - (time.monotonic() - last_flush))
            try:
                row = self._queue.get(timeout=timeout or 0.1)
                batch.append(row)
            except queue.Empty:
                pass

            should_flush = len(batch) >= self._flush_batch_size or (
                batch and (time.monotonic() - last_flush) >= self._flush_interval
            )
            if should_flush:
                self._flush(batch)
                batch = []
                last_flush = time.monotonic()

        # Drain remaining queued items and flush on shutdown.
        while not self._queue.empty():
            batch.append(self._queue.get_nowait())
        if batch:
            self._flush(batch)

    def _flush(self, batch: list[dict[str, Any]]) -> None:
        table = pa.Table.from_pylist(batch, schema=SPAN_SCHEMA)
        file_path = self._data_dir / f"spans-{int(time.time())}-{uuid.uuid4().hex[:8]}.parquet"
        pq.write_table(table, file_path)
