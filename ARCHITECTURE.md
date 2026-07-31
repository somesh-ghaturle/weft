# Architecture Deep Dive

This document provides an in-depth look at Weft's design, data flow, and key architectural decisions.

---

## System Overview

### High-Level Data Flow

```
┌─ Client SDKs (Python, JS, OTel)
│
├─ OTLP/HTTP Endpoint (FastAPI)
│  └─ Protobuf Deserialization
│
├─ Background Writer (Singleton Thread)
│  ├─ Enqueue Span Row (Thread-safe Queue)
│  └─ Batch + Flush to Parquet
│
├─ Parquet Files (Columnar Storage)
│  └─ 1 file per flush (~2 seconds, or 500 spans)
│
├─ DuckDB Query Engine (Read-Only)
│  └─ On-demand queries against Parquet glob
│
├─ Metadata Database (SQLite or PostgreSQL)
│  ├─ Prompt Versions & Labels
│  ├─ Datasets & Items
│  └─ Eval Runs & Results
│
└─ Frontend (Next.js)
   ├─ Trace List (GET /traces)
   ├─ Waterfall Detail (GET /traces/{id})
   ├─ Prompt Manager (GET/POST /prompts)
   └─ Dataset Browser (GET /datasets)
```

---

## Component Deep Dives

### 1. OTLP Ingestion Endpoint

**File:** `backend/app/ingestion/otlp.py`

**Responsibilities:**
- Accept binary OTLP ExportTraceServiceRequest (protobuf)
- Parse resource metadata (service.name) and spans
- Extract GenAI semantic convention attributes
- Enqueue to background writer
- Return success response (ExportTraceServiceResponse)

**Key Functions:**

```python
def build_router(writer: SpanWriter) -> APIRouter:
    """Create FastAPI router for /v1/traces endpoint."""
    @router.post("/v1/traces")
    async def export_traces(request: Request) -> Response:
        # Deserialize protobuf
        body = await request.body()
        otlp_request = ExportTraceServiceRequest()
        otlp_request.ParseFromString(body)
        
        # Process resource → spans
        for resource_spans in otlp_request.resource_spans:
            service_name = extract_service_name(resource_spans.resource)
            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
                    row = _span_to_row(span, service_name)
                    writer.enqueue(row)  # Non-blocking enqueue
        
        # Return protobuf response
        return Response(content=response.SerializeToString(), ...)
```

**Why This Design:**
- **Non-blocking**: endpoint returns immediately; writer processes async
- **Standard protocol**: any OTel SDK/Collector can send traces
- **Semantic extraction**: captures GenAI attributes (model, tokens) for observability

**Tradeoffs:**
- Protobuf parsing overhead (small)
- Tight coupling to protobuf schema (offset by vendor neutrality)

---

### 2. Background Writer (Single Thread Pattern)

**File:** `backend/app/storage/writer.py`

**Problem It Solves:**
DuckDB is a poor concurrent writer; multiple threads trying to flush Parquet simultaneously cause lock contention and crashes. Solution: all spans funnel through a single background thread.

**Architecture:**

```python
class SpanWriter:
    def __init__(self, data_dir: Path, flush_interval_seconds=2.0, flush_batch_size=500):
        self._queue = queue.Queue()  # Thread-safe, unbounded
        self._thread = threading.Thread(target=self._run, daemon=True)
    
    def start(self):
        self._thread.start()
    
    def enqueue(self, span_row: dict):
        self._queue.put(span_row)  # Producer (request handlers)
    
    def _run(self):
        """Consumer (background thread)."""
        batch = []
        while not self._stop_event.is_set():
            try:
                row = self._queue.get(timeout=0.1)
                batch.append(row)
            except queue.Empty:
                pass
            
            # Flush on timer or batch size
            if len(batch) >= self._flush_batch_size or time_since_flush > interval:
                self._flush(batch)
                batch = []
    
    def _flush(self, batch):
        """Write batch to Parquet using PyArrow."""
        table = pa.Table.from_pylist(batch, schema=SPAN_SCHEMA)
        file_path = data_dir / f"spans-{time.time()}-{uuid.uuid4().hex[:8]}.parquet"
        pq.write_table(table, file_path)
```

**Flow:**

```
Request Thread 1      Request Thread 2      Request Thread N
         │                   │                       │
         └─────────────────────────────────────────┘
                   enqueue(span_row)
                           │
                    [Thread-Safe Queue]
                           │
                  Background Writer Thread
                           │
              ┌────────────┴────────────┐
              │                         │
        Timer Expired              Batch Full
        (2 seconds)                (500 spans)
              │                         │
              └────────────┬────────────┘
                           │
                    _flush(batch)
                           │
                  PyArrow Table.from_pylist()
                           │
            pq.write_table(table, file_path)
                           │
                    Parquet File (.parquet)
```

**Key Properties:**

| Property | Value | Why |
|----------|-------|-----|
| **Concurrency** | Single consumer | Avoids DuckDB lock contention |
| **Queue Type** | Unbounded | Producers never block |
| **Flush Strategy** | Time + size | Balances latency vs. throughput |
| **Fault Tolerance** | Daemon thread | Doesn't block shutdown |
| **Data Loss** | Possible | Queue lost on crash (acceptable for observability) |

**Tradeoffs:**
- **Pro**: Simple, fast, no database locks
- **Con**: Not transactional; spans in queue are lost on crash

---

### 3. Parquet Storage & Query

**Files:** `backend/app/storage/query.py`, `backend/app/storage/writer.py`

**Schema:**

```python
SPAN_SCHEMA = pa.schema([
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
])
```

**Query Examples:**

```python
def list_traces(data_dir: Path, limit: int = 50) -> list[dict]:
    """Aggregate spans into traces."""
    con = duckdb.connect(database=":memory:")
    rows = con.execute(f"""
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
        LIMIT {limit}
    """).fetchall()
```

**Why Parquet:**
- **Columnar**: fast aggregations (group by trace_id)
- **Compression**: ~1/10 the size of raw JSON
- **Self-describing**: schema embedded in files
- **Portable**: read from Python, R, Java, Spark, DuckDB, etc.

**Why DuckDB (not PostgreSQL):**
- **Zero setup**: file-based, no server needed
- **Fast aggregations**: vectorized execution
- **Upgrade path**: can migrate to ClickHouse/Snowflake later via same SQL

**Scaling Concerns:**
- Single DuckDB connection per query (okay; DuckDB is single-threaded)
- Parquet glob grows over time (~1 query scans N files)
- **Future**: partition by date, implement retention policies

---

### 4. Metadata Database

**File:** `backend/app/metadata/models.py`

**Schema Highlights:**

```python
class Prompt:
    id: str
    name: str (unique)
    versions: List[PromptVersion]
    labels: List[Label]

class PromptVersion:
    id: str
    prompt_id: str (FK)
    version_number: int (unique per prompt)
    template: str
    config: dict (JSON)
    created_at: timestamp
    # IMMUTABLE: once created, never changes

class Label:
    id: str
    prompt_id: str (FK)
    name: str (unique per prompt)
    version_id: str (FK → PromptVersion)
    updated_at: timestamp
    # MUTABLE: can point to different version
    # Atomic reassignment: single UPDATE row

class Dataset:
    id: str
    name: str (unique)
    description: str
    items: List[DatasetItem]

class DatasetItem:
    id: str
    dataset_id: str (FK)
    input: dict (JSON)
    expected_output: dict (JSON, nullable)
    source_trace_id: str (nullable, for trace promotion)

class EvalRun:
    id: str
    dataset_id: str (FK)
    evaluator_name: str
    status: str ("pending" | "running" | "completed" | "failed")
    results: dict (JSON: mean_score, item_count, items[])
    created_at, completed_at: timestamp
```

**Design Decision: Label Reassignment Atomicity**

The SDK's hot path is:
```python
tracer.get_prompt(name="customer-support", label="production")
```

This becomes:
```sql
SELECT version.* FROM labels
WHERE prompt_id = (SELECT id FROM prompts WHERE name = ?)
  AND name = ?
ORDER BY updated_at DESC
LIMIT 1
```

**Why single row?**
- Reassigning `Label.version_id` is a single UPDATE
- No race conditions or "label points to two versions" transient state
- Reads are always consistent

**Alternative (rejected):**
```
Prompt ← VersionStack
         └─ [v1, v2, v3]  ← Label pointer
```
This requires JOIN and has ambiguity during reassignment.

---

### 5. Evaluator Interface

**File:** `backend/app/eval/evaluator.py`

**Protocol:**

```python
class Evaluator(Protocol):
    name: str
    
    def score(self, item: dict[str, Any], output: Any) -> EvalResult:
        """Score system output against item.
        
        item: {"input": ..., "expected_output": ...}
        output: whatever the system produced
        
        Returns: EvalResult(score=0.0-1.0, reasoning="...")
        """
        ...

@dataclass
class EvalResult:
    score: float
    reasoning: str
```

**Built-in Implementations:**

| Evaluator | Logic | Config |
|-----------|-------|--------|
| `exact_match` | `output == item["expected_output"]` | None |
| `regex` | `pattern.search(str(output)) is not None` | `{"pattern": "..."}` |
| `schema_validity` | Output dict has all required_keys | `{"required_keys": [...]}` |
| `llm_judge` | LLM evaluates output (stubbed) | `{"judge_prompt": "..."}` |

**Extending for Phase 3 (RAG Evaluators):**

```python
class TruLensContextRelevance:
    """Does retrieved context actually answer the question?"""
    name = "rag/context_relevance"
    
    def __init__(self, call_judge_model):
        self.call_judge = call_judge_model
    
    def score(self, item: dict, output: dict) -> EvalResult:
        # output = {"context": [...], "answer": "..."}
        prompt = f"Q: {item['input']}\nContext: {output['context']}\nRelevant? 1-10"
        score_str = self.call_judge(prompt)
        score = float(score_str) / 10
        return EvalResult(score=score, reasoning="...")
```

**Why Protocol (not ABC):**
- Structural typing: don't need to inherit
- Easier to compose and mock
- Matches Python idioms

---

### 6. Frontend Architecture

**Framework:** Next.js 16 (App Router)

**Structure:**
```
app/
├── layout.tsx          # Root layout (metadata, styles)
├── page.tsx            # Trace list (server component)
├── traces/
│   └── [traceId]/
│       └── page.tsx    # Trace detail (server component)
└── lib/
    └── api.ts          # Fetch wrapper (client-side)
```

**Data Flow:**

```
Page.tsx (Server Component)
  └─ fetch() → Backend /traces API
     └─ await listTraces()
        └─ Pass to Component JSX
           └─ Render <table> with traces
              └─ <Link href={`/traces/${traceId}`}>
```

**Waterfall Component:**

```tsx
function WaterfallRow({ span, depth, traceStart, traceDuration }) {
    // Calculate position and width as % of trace duration
    const offsetPct = (span.start_unix_nano - traceStart) / traceDuration * 100
    const widthPct = (span.duration_ms * 1e6) / traceDuration * 100
    
    // Render nested tree structure
    return (
        <div style={{ paddingLeft: depth * 16 }}>
            <div style={{ position: 'relative', height: 18 }}>
                {/* Bar representing span duration */}
                <div style={{
                    position: 'absolute',
                    left: `${offsetPct}%`,
                    width: `${widthPct}%`,
                    backgroundColor: KIND_COLORS[span.kind],
                }}/>
            </div>
            {/* Recursively render child spans */}
            {renderChildren(span.span_id, tree, depth + 1, traceStart, traceDuration)}
        </div>
    )
}
```

**Key Design:**
- Server-side rendering for trace list (SEO, fast initial load)
- Waterfall bars: proportional to actual wall-clock time
- Color coding by span kind (client, server, internal, etc.)

---

## Data Flow Scenarios

### Scenario 1: Sending a Trace

```
Python App
  │
  ├─ tracer.start_span("chat") as span
  │  └─ span.set_attribute("gen_ai.system", "openai")
  │
  ├─ tracer.export()
  │  │
  │  └─ Tracer.export()
  │     ├─ Convert Span → protobuf PbSpan
  │     ├─ Wrap in ExportTraceServiceRequest
  │     └─ POST /v1/traces (binary protobuf)
  │
  └─ Backend /v1/traces
     ├─ Deserialize protobuf
     ├─ Extract span, resource, attributes
     ├─ Convert to dict row (with GenAI attrs)
     └─ writer.enqueue(row)  ← RETURNS IMMEDIATELY
        │
        └─ [Background Writer Thread]
           ├─ Accumulate in batch
           ├─ Every 500 spans or 2 seconds
           ├─ Convert batch → PyArrow Table
           └─ pq.write_table() → .parquet file
```

**Latency:**
- Enqueue: O(1), <1ms
- Flush: O(batch_size), ~50ms for 500 spans
- **Total end-to-end**: <2 seconds (usually)

---

### Scenario 2: Querying a Trace

```
Frontend (Next.js)
  │
  ├─ GET /traces/{traceId}
  │  └─ Server Component calls getTrace()
  │
  └─ Backend GET /traces/{traceId}
     ├─ Open DuckDB in-memory connection
     ├─ SELECT * FROM read_parquet('.../*.parquet')
     │        WHERE trace_id = ?
     │        ORDER BY start_time_unix_nano ASC
     │
     └─ DuckDB
        ├─ Scan all .parquet files (glob)
        ├─ Filter by trace_id (vectorized)
        ├─ Return rows sorted by start time
        │
        └─ Return JSON array of spans
           │
           └─ Frontend renders waterfall
              ├─ Build tree: parent_span_id → children
              ├─ Recursively render WaterfallRow
              └─ Position bars by start time + duration
```

**Latency:**
- DuckDB scan: O(N parquet files), ~100ms - 1s
- Render: O(span_count), <100ms

---

### Scenario 3: Updating a Prompt Label

```
Client
  │
  └─ POST /prompts/{prompt_id}/labels
     {name: "production", version_id: "v2"}
     │
     └─ Backend
        ├─ Look up Prompt
        ├─ Look up PromptVersion
        ├─ Check: version.prompt_id == prompt.id (consistency)
        │
        └─ SQL Transaction
           ├─ Check if label exists
           ├─ If exists: UPDATE labels SET version_id = ?
           ├─ If new: INSERT into labels (prompt_id, name, version_id)
           └─ COMMIT
              │
              └─ Return updated label
                 │
                 └─ SDK (or human) reads:
                    GET /prompts/customer-support/labels/production
                    ← Returns version with "production" pointing to v2
```

**Atomicity:**
- Single UPDATE = atomic
- No transient "label points to v1 and v2" state

---

## Deployment Topologies

### Single-Instance (Development)

```
        App Machine
┌────────────────────────────┐
│ Backend (Gunicorn)         │
│ ├─ OTLP Endpoint           │
│ ├─ Background Writer       │
│ └─ Query Handler           │
│                            │
│ Frontend (Next.js)         │
│                            │
│ Data (local filesystem)    │
│ ├─ data/*.parquet          │
│ └─ weft.db (SQLite)        │
└────────────────────────────┘
```

### Multi-Instance (Production)

```
                Clients
      ┌─────┬─────┬─────┐
      │ App │ App │ App │
      └──┬──┴──┬──┴──┬──┘
         │     │     │
      ┌──▼─────▼─────▼──┐
      │   Load Balancer  │
      │   (nginx/haproxy)│
      └──┬──┴──┬──┴──┬──┘
         │     │     │
    ┌────▼──┐ ┌─▼───┐ ┌───▼────┐
    │Backend│ │Back │ │Backend  │
    │  #1   │ │end  │ │  #3     │
    │       │ │ #2  │ │         │
    └────┬──┘ └─┬───┘ └───┬────┘
         │     │     │
         └─────┬──┬──┘
               │  │
          ┌────▼──▼────┐
          │   Shared   │
          │ NFS/S3     │
          │ (Parquet)  │
          └────────────┘
          
          ┌──────────────┐
          │ PostgreSQL   │
          │ (Metadata)   │
          └──────────────┘
```

**Key Points:**
- Each backend instance has its own Background Writer
- All writers flush to **shared storage** (NFS or S3)
- Metadata DB is **shared** (PostgreSQL)
- Queries read from shared Parquet glob

**Tradeoffs:**
- **Pro**: Horizontal scaling, fault tolerance
- **Con**: Complex deployment, shared storage cost

---

## Performance Characteristics

### Ingestion

| Metric | Value | Notes |
|--------|-------|-------|
| Enqueue latency | <1ms | Non-blocking, thread-safe queue |
| Batch flush latency | 50-200ms | 500 spans to Parquet |
| End-to-end latency | <2 sec | Flush interval + queue drain |
| Throughput | ~10k spans/sec | Single writer, 500 spans/batch |

### Query

| Metric | Value | Notes |
|--------|-------|-------|
| DuckDB scan | 100ms - 1s | Depends on # parquet files |
| Aggregate (e.g., traces) | 50-200ms | Vectorized GROUP BY |
| Point query (e.g., get_trace) | 100-500ms | Filter + sort on disk |

### Storage

| Metric | Value | Notes |
|--------|-------|-------|
| Span size (Parquet) | ~100 bytes | Compressed, columnar |
| 1M spans storage | ~100MB | Rough estimate |
| Parquet file size | ~5-50MB | 500-5000 spans per file |

---

## Security Considerations

### Currently (Phase 0-2)

- **No authentication**: all endpoints are public
- **No encryption**: data at rest (Parquet) is unencrypted
- **No rate limiting**: no DDoS protection

### Future (Phase 3+)

- API keys or OAuth for /v1/traces endpoint
- TLS everywhere
- Rate limiting per key
- Audit logging
- RBAC for prompts/datasets/evals

---

## Observability (Dogfooding)

Weft should instrument itself:

```python
# In backend/app/ingestion/otlp.py
from weft import Tracer, SpanKind

internal_tracer = Tracer(
    endpoint="http://localhost:9999",  # Second Weft instance
    service_name="weft-backend"
)

@router.post("/v1/traces")
async def export_traces(request: Request):
    with internal_tracer.start_span("export_traces") as span:
        span.set_attribute("span_count", len(otlp_request.resource_spans))
        # ... rest of handler ...
```

This creates a **second Weft instance** that monitors the first — "Weft observing Weft."

---

## Future Directions

### Phase 3+: Advanced Evaluators

- RAG triad evaluators (TruLens-style)
- Similarity scoring (embeddings)
- Custom Python evaluator plugins

### Scaling & Performance

- Partitioned Parquet (by date, service, etc.)
- Columnar indices
- ClickHouse backend option
- Distributed tracing (spans across services)

### Integrations

- Datadog, New Relic exporters
- Grafana datasource plugin
- Slack/webhook alerts for anomalies

---

## References

- [OpenTelemetry Protocol](https://opentelemetry.io/docs/reference/specification/protocol/)
- [Parquet Format](https://parquet.apache.org/)
- [DuckDB SQL](https://duckdb.org/docs/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
