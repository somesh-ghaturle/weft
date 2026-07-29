"""OTLP/HTTP trace ingestion endpoint.

Accepts a standard OTLP ExportTraceServiceRequest (protobuf), matching the
OpenTelemetry wire format so any OTel SDK, OTel Collector, or our own SDK can
send spans here without a proprietary protocol.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan
from opentelemetry.proto.trace.v1.trace_pb2 import Status as PbStatus

from app.storage.writer import SpanWriter

router = APIRouter()

_SPAN_KIND_NAMES = {
    PbSpan.SPAN_KIND_UNSPECIFIED: "unspecified",
    PbSpan.SPAN_KIND_INTERNAL: "internal",
    PbSpan.SPAN_KIND_SERVER: "server",
    PbSpan.SPAN_KIND_CLIENT: "client",
    PbSpan.SPAN_KIND_PRODUCER: "producer",
    PbSpan.SPAN_KIND_CONSUMER: "consumer",
}


def _attr_value(value) -> object:
    kind = value.WhichOneof("value")
    if kind is None:
        return None
    if kind == "string_value":
        return value.string_value
    if kind == "int_value":
        return value.int_value
    if kind == "double_value":
        return value.double_value
    if kind == "bool_value":
        return value.bool_value
    return str(getattr(value, kind))


def _attrs_to_dict(attributes) -> dict[str, object]:
    return {a.key: _attr_value(a.value) for a in attributes}


def _span_to_row(span: PbSpan, service_name: str) -> dict[str, object]:
    attrs = _attrs_to_dict(span.attributes)
    start_ns = span.start_time_unix_nano
    end_ns = span.end_time_unix_nano
    duration_ms = (end_ns - start_ns) / 1_000_000 if end_ns >= start_ns else 0.0

    return {
        "trace_id": span.trace_id.hex(),
        "span_id": span.span_id.hex(),
        "parent_span_id": span.parent_span_id.hex() if span.parent_span_id else "",
        "name": span.name,
        "kind": _SPAN_KIND_NAMES.get(span.kind, "unspecified"),
        "start_time_unix_nano": start_ns,
        "end_time_unix_nano": end_ns,
        "duration_ms": duration_ms,
        "status_code": PbStatus.StatusCode.Name(span.status.code),
        "service_name": service_name,
        "gen_ai_system": str(attrs.get("gen_ai.system", "")),
        "gen_ai_request_model": str(attrs.get("gen_ai.request.model", "")),
        "gen_ai_usage_input_tokens": int(attrs.get("gen_ai.usage.input_tokens") or 0),
        "gen_ai_usage_output_tokens": int(attrs.get("gen_ai.usage.output_tokens") or 0),
        "attributes_json": json.dumps(attrs, default=str),
    }


def build_router(writer: SpanWriter) -> APIRouter:
    @router.post("/v1/traces")
    async def export_traces(request: Request) -> Response:
        body = await request.body()
        otlp_request = ExportTraceServiceRequest()
        otlp_request.ParseFromString(body)

        span_count = 0
        for resource_spans in otlp_request.resource_spans:
            service_name = ""
            for attr in resource_spans.resource.attributes:
                if attr.key == "service.name":
                    service_name = _attr_value(attr.value)
                    break
            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
                    writer.enqueue(_span_to_row(span, str(service_name)))
                    span_count += 1

        response = ExportTraceServiceResponse()
        return Response(
            content=response.SerializeToString(),
            media_type="application/x-protobuf",
            headers={"X-Weft-Spans-Ingested": str(span_count)},
        )

    return router
