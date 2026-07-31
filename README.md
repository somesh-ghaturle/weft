# Weft

**OTel-native LLM observability — unified traces, evals, and prompts in one self-hosted binary.**

Weft is a lightweight alternative to Langfuse, Phoenix, and OpenObserve for teams that want:
- **Vendor-neutral ingestion**: speaks only OTLP (OpenTelemetry Protocol)
- **No vendor lock-in**: everything self-hosted, everything portable
- **Unified platform**: traces + evaluations + prompt versioning in one place
- **Low operational overhead**: DuckDB + Parquet columnar storage, no heavy database

## Architecture

- **Backend**: Python/FastAPI
  - OTLP/HTTP `/v1/traces` endpoint (accepts any OTel SDK or Collector)
  - Span ingestion → single background writer → Parquet files (DuckDB)
  - Trace query API
  - Prompt versioning + label-based resolution
  - Dataset CRUD + eval runner with pluggable Evaluator interface
- **Frontend**: Next.js/React
  - Trace list with filtering
  - Interactive waterfall view (nested span bars, duration, status)
- **SDK**: Python tracer + OTLP exporter (manual span helpers, zero external deps beyond opentelemetry-proto)

## Quick Start

### Prerequisites
- Python 3.14+
- Node.js 20+
- pip, npm

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
WEFT_DATA_DIR=./data uvicorn app.api.main:app --port 8000
```

Health check: `curl http://127.0.0.1:8000/healthz`

### Frontend

```bash
cd frontend
npm install
WEFT_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Open http://127.0.0.1:3000 to see the trace list and waterfall views.

### Send a Test Trace

```python
from weft import Tracer, SpanKind

tracer = Tracer(endpoint="http://127.0.0.1:8000", service_name="my-app")

with tracer.start_span("chat_completion", kind=SpanKind.CLIENT) as span:
    span.set_attribute("gen_ai.system", "openai")
    span.set_attribute("gen_ai.request.model", "gpt-4")
    span.set_attribute("gen_ai.usage.input_tokens", 150)
    span.set_attribute("gen_ai.usage.output_tokens", 45)
    # ... your code here ...

tracer.export()  # export to backend
```

## API

### Traces
- `GET /traces?limit=50` — list recent traces
- `GET /traces/{trace_id}` — get all spans in a trace

### Prompts
- `GET /prompts` — list prompts
- `POST /prompts` — create prompt
- `POST /prompts/{id}/versions` — create immutable version
- `POST /prompts/{id}/labels` — create/update label (points to a version)
- `GET /prompts/{name}/labels/{label}` — resolve prompt by label (SDK hot path)

### Datasets
- `GET /datasets` — list datasets
- `POST /datasets` — create dataset
- `POST /datasets/{id}/items` — add item (or promote trace as item)

### Evaluators
- `POST /eval-runs` — run evaluator on dataset items
- `GET /eval-runs/{id}` — get eval results

Built-in evaluators: `exact_match`, `regex`, `schema_validity`, `llm_judge` (stubbed, supply your own LLM call).

## Phases

- **Phase 0**: OTLP ingestion → Parquet → query ✅
- **Phase 1**: Trace UI (waterfall) ✅
- **Phase 2**: Prompts, datasets, eval runner ✅
- **Phase 3**: RAG triad evaluators (TruLens-style, Phase 3)
- **Phase 4**: Scale-out (ClickHouse upgrade path), optional JS/TS SDK

## Design Decisions

- **Single background writer**: DuckDB is a poor concurrent writer; all ingestion goes through one writer that batches and flushes to Parquet
- **Atomic label reassignment**: Prompt labels are single-row UPDATEs in SQL, so SDK reads (label resolution) are a single lookup with no race conditions
- **Pluggable Evaluator interface**: new evaluators are just new implementations, not a rewrite of the eval machinery
- **No vendor lock-in**: OTLP is the only wire protocol; every byte is portable to any OTLP collector

## License

MIT
