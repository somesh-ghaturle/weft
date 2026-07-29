"""In-memory span representation, independent of the OTLP wire format."""

from __future__ import annotations

import enum
import os
import time
from dataclasses import dataclass, field


class SpanKind(enum.Enum):
    UNSPECIFIED = "unspecified"
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class StatusCode(enum.Enum):
    UNSET = "STATUS_CODE_UNSET"
    OK = "STATUS_CODE_OK"
    ERROR = "STATUS_CODE_ERROR"


def new_trace_id() -> str:
    """16 random bytes as 32 hex chars, per the W3C trace-context / OTLP trace_id spec."""
    return os.urandom(16).hex()


def new_span_id() -> str:
    """8 random bytes as 16 hex chars, per the W3C trace-context / OTLP span_id spec."""
    return os.urandom(8).hex()


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    kind: SpanKind = SpanKind.INTERNAL
    start_time_unix_nano: int = field(default_factory=time.time_ns)
    end_time_unix_nano: int = 0
    status_code: StatusCode = StatusCode.UNSET
    attributes: dict[str, object] = field(default_factory=dict)

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def set_status(self, status_code: StatusCode) -> None:
        self.status_code = status_code

    def end(self) -> None:
        if self.end_time_unix_nano == 0:
            self.end_time_unix_nano = time.time_ns()
