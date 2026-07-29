"""Converts weft.Span objects to OTLP protobuf and POSTs them to a collector endpoint."""

from __future__ import annotations

import urllib.error
import urllib.request

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan
from opentelemetry.proto.trace.v1.trace_pb2 import Status as PbStatus

from weft.span import Span, SpanKind, StatusCode

_SPAN_KIND_TO_PB = {
    SpanKind.UNSPECIFIED: PbSpan.SPAN_KIND_UNSPECIFIED,
    SpanKind.INTERNAL: PbSpan.SPAN_KIND_INTERNAL,
    SpanKind.SERVER: PbSpan.SPAN_KIND_SERVER,
    SpanKind.CLIENT: PbSpan.SPAN_KIND_CLIENT,
    SpanKind.PRODUCER: PbSpan.SPAN_KIND_PRODUCER,
    SpanKind.CONSUMER: PbSpan.SPAN_KIND_CONSUMER,
}

_STATUS_CODE_TO_PB = {
    StatusCode.UNSET: PbStatus.STATUS_CODE_UNSET,
    StatusCode.OK: PbStatus.STATUS_CODE_OK,
    StatusCode.ERROR: PbStatus.STATUS_CODE_ERROR,
}


def _any_value(value: object) -> AnyValue:
    av = AnyValue()
    if isinstance(value, bool):
        av.bool_value = value
    elif isinstance(value, int):
        av.int_value = value
    elif isinstance(value, float):
        av.double_value = value
    else:
        av.string_value = str(value)
    return av


def _to_pb_span(span: Span) -> PbSpan:
    pb = PbSpan(
        trace_id=bytes.fromhex(span.trace_id),
        span_id=bytes.fromhex(span.span_id),
        name=span.name,
        kind=_SPAN_KIND_TO_PB[span.kind],
        start_time_unix_nano=span.start_time_unix_nano,
        end_time_unix_nano=span.end_time_unix_nano,
        attributes=[KeyValue(key=k, value=_any_value(v)) for k, v in span.attributes.items()],
        status=PbStatus(code=_STATUS_CODE_TO_PB[span.status_code]),
    )
    if span.parent_span_id:
        pb.parent_span_id = bytes.fromhex(span.parent_span_id)
    return pb


class OTLPExporter:
    """Posts finished spans to a Weft (or any OTLP/HTTP) collector's /v1/traces endpoint."""

    def __init__(self, endpoint: str, service_name: str, timeout_seconds: float = 5.0):
        self._endpoint = endpoint.rstrip("/") + "/v1/traces"
        self._service_name = service_name
        self._timeout = timeout_seconds

    def export(self, spans: list[Span]) -> None:
        if not spans:
            return
        resource = Resource(
            attributes=[KeyValue(key="service.name", value=_any_value(self._service_name))]
        )
        resource_spans = ResourceSpans(
            resource=resource,
            scope_spans=[ScopeSpans(spans=[_to_pb_span(s) for s in spans])],
        )
        request = ExportTraceServiceRequest(resource_spans=[resource_spans])
        body = request.SerializeToString()

        http_request = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={"Content-Type": "application/x-protobuf"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout) as response:
                response.read()
        except urllib.error.URLError as exc:
            raise RuntimeError(f"weft: failed to export spans to {self._endpoint}: {exc}") from exc
