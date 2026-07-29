"""User-facing tracer: start_span() context manager + GenAI span helpers."""

from __future__ import annotations

import contextlib
import contextvars
from typing import Iterator

from weft.exporter import OTLPExporter
from weft.span import Span, SpanKind, StatusCode, new_span_id, new_trace_id

_current_span: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
    "weft_current_span", default=None
)


class Tracer:
    """Builds spans and exports them to a Weft-compatible OTLP/HTTP endpoint.

    Spans are exported synchronously on `end()`/context-manager exit — Phase 0 favors a
    simple, immediately-visible pipeline over background batching (the backend's own
    SpanWriter already batches on the receiving side).
    """

    def __init__(self, endpoint: str, service_name: str):
        self._exporter = OTLPExporter(endpoint, service_name)

    @contextlib.contextmanager
    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, object] | None = None,
    ) -> Iterator[Span]:
        parent = _current_span.get()
        trace_id = parent.trace_id if parent else new_trace_id()
        parent_span_id = parent.span_id if parent else ""

        span = Span(
            name=name,
            trace_id=trace_id,
            span_id=new_span_id(),
            parent_span_id=parent_span_id,
            kind=kind,
            attributes=dict(attributes or {}),
        )
        token = _current_span.set(span)
        try:
            yield span
        except Exception:
            span.set_status(StatusCode.ERROR)
            raise
        else:
            if span.status_code == StatusCode.UNSET:
                span.set_status(StatusCode.OK)
        finally:
            _current_span.reset(token)
            span.end()
            self._exporter.export([span])

    def start_llm_span(
        self,
        name: str,
        system: str,
        model: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ):
        """Convenience wrapper for start_span() pre-populated with OTel GenAI semantic
        convention attributes, so callers don't need to know the raw attribute keys."""
        attributes: dict[str, object] = {
            "gen_ai.system": system,
            "gen_ai.request.model": model,
        }
        if input_tokens is not None:
            attributes["gen_ai.usage.input_tokens"] = input_tokens
        if output_tokens is not None:
            attributes["gen_ai.usage.output_tokens"] = output_tokens
        return self.start_span(name, kind=SpanKind.CLIENT, attributes=attributes)
