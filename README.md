# Weft

**OTel-native LLM observability — unified traces, evals, and prompts in one self-hosted binary.**

Weft is a lightweight alternative to Langfuse, Phoenix, and OpenObserve for teams that want:
- **Vendor-neutral ingestion**: speaks only OTLP (OpenTelemetry Protocol)
- **No vendor lock-in**: everything self-hosted, everything portable
- **Unified platform**: traces + evaluations + prompt versioning in one place
- **Low operational overhead**: DuckDB + Parquet columnar storage, no heavy database

## System Architecture

```mermaid
graph TB
    subgraph "Client Applications"
        A["Python App<br/>(with Weft SDK)"]
        B["OpenAI SDK<br/>(auto-instrumented)"]
        C["OpenTelemetry<br/>Collector"]
    end

    subgraph "Weft Backend (Python/FastAPI)"
        D["OTLP/HTTP Endpoint<br/>/v1/traces"]
        E["Background Writer<br/>(Single Thread)"]
        F["DuckDB Engine"]
        G["Parquet Files<br/>(Columnar Storage)"]
        
        H["Prompt Service<br/>GET /prompts"]
        I["Dataset Service<br/>GET /datasets"]
        J["Eval Service<br/>POST /eval-runs"]
        K["SQLite/Postgres<br/>Metadata DB"]
    end

    subgraph "Frontend (Next.js)"
        L["Trace List Page"]
        M["Waterfall Detail View"]
        N["Prompt Manager"]
        O["Dataset Browser"]
    end

    subgraph "Data Layer"
        P["Parquet Filesystem<br/>~backend/data/"]
        Q["Metadata SQLite<br/>~backend/weft.db"]
    end

    A -->|"OTLP Protobuf"| D
    B -->|"OTLP Protobuf"| D
    C -->|"OTLP Protobuf"| D
    
    D -->|"Enqueue Span"| E
    E -->|"Batch Write"| F
    F -->|"Write Files"| G
    G -->|"Read Parquet"| F
    
    H -->|"Read/Write"| K
    I -->|"Read/Write"| K
    J -->|"Read/Write"| K
    
    F -->|"Query Spans"| H
    F -->|"Query Spans"| I
    F -->|"Query Spans"| J
    
    L -->|"GET /traces"| H
    M -->|"GET /traces/{id}"| H
    N -->|"GET/POST /prompts"| H
    O -->|"GET /datasets"| I
    
    G -.->|"Data"| P
    K -.->|"Data"| Q
```

### Key Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **OTLP Endpoint** | Accepts traces from any OTel SDK | FastAPI + protobuf |
| **Background Writer** | Singleton pattern to avoid DuckDB contention | Python threading |
| **Parquet Storage** | Column-oriented trace data (fast queries, small size) | DuckDB + PyArrow |
| **Metadata DB** | Prompt versions, labels, datasets, eval runs | SQLAlchemy + SQLite/Postgres |
| **Frontend** | Interactive trace exploration | Next.js + React |

---

## Getting Started

### Level 1: Quick Start (5 minutes)

Perfect for trying Weft locally.

#### Setup

```bash
# Clone the repo
git clone https://github.com/somesh-ghaturle/weft.git
cd weft

# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Frontend setup (new terminal)
cd frontend
npm install
```

#### Run

**Terminal 1 — Backend:**
```bash
cd backend
source .venv/bin/activate
WEFT_DATA_DIR=./data uvicorn app.api.main:app --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
WEFT_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

**Terminal 3 — Send a test trace:**
```bash
cd backend
source .venv/bin/activate
python - <<'EOF'
from weft import Tracer, SpanKind

tracer = Tracer(endpoint="http://127.0.0.1:8000", service_name="quick-test")
with tracer.start_span("hello", kind=SpanKind.CLIENT) as span:
    span.set_attribute("gen_ai.system", "openai")
    span.set_attribute("gen_ai.usage.input_tokens", 100)
tracer.export()
print("✓ Trace sent!")
EOF
```

Open http://127.0.0.1:3000 → you'll see your trace in the list → click it to see the waterfall.

---

### Level 2: Production Setup (20 minutes)

For deployment to a shared environment with persistence.

#### 1. Environment Configuration

Create `.env.backend`:
```bash
# Data storage (must be persistent volume if multi-instance)
WEFT_DATA_DIR=/var/lib/weft/data

# Metadata DB (PostgreSQL for production; SQLite for single-instance)
DATABASE_URL=postgresql://user:pass@localhost/weft_metadata

# OTLP server settings
OTLP_BIND_HOST=0.0.0.0
OTLP_PORT=8000

# Frontend URL (for CORS, if needed)
WEFT_FRONTEND_URL=https://traces.example.com
```

Create `.env.frontend`:
```bash
# Backend API endpoint (from clients' perspective)
WEFT_BACKEND_URL=https://api.example.com

# Analytics/telemetry (optional)
NEXT_PUBLIC_ENVIRONMENT=production
```

#### 2. Database Setup (PostgreSQL)

```bash
# Create database
psql -U postgres -c "CREATE DATABASE weft_metadata;"

# Initialize schema (backend does this on startup via SQLAlchemy)
cd backend
source .venv/bin/activate
python -c "from app.metadata.db import init_db; init_db()"
```

#### 3. Start Backend

```bash
cd backend
source .venv/bin/activate
export DATABASE_URL=postgresql://user:pass@db:5432/weft_metadata
export WEFT_DATA_DIR=/var/lib/weft/data
mkdir -p $WEFT_DATA_DIR

# Using uvicorn (development) or gunicorn (production)
gunicorn app.api.main:app --workers 4 --bind 0.0.0.0:8000
```

#### 4. Start Frontend

```bash
cd frontend
npm run build
export WEFT_BACKEND_URL=https://api.example.com
npm start  # runs on port 3000
```

#### 5. Configure Reverse Proxy (nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 443 ssl http2;
    server_name traces.example.com;

    ssl_certificate /etc/letsencrypt/live/traces.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/traces.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
    }
}
```

---

### Level 3: Integration Guide (Detailed Examples)

#### 3.1 Python SDK

**Installation:**
```bash
pip install -e sdk/python
```

**Basic Usage:**
```python
from weft import Tracer, SpanKind, StatusCode
import time

# Initialize tracer
tracer = Tracer(
    endpoint="http://127.0.0.1:8000",
    service_name="my-llm-app"
)

# Create a span
with tracer.start_span("chat_completion", kind=SpanKind.CLIENT) as span:
    # Set semantic convention attributes
    span.set_attribute("gen_ai.system", "openai")
    span.set_attribute("gen_ai.request.model", "gpt-4")
    
    # Simulate API call
    time.sleep(0.5)
    
    # Set token usage
    span.set_attribute("gen_ai.usage.input_tokens", 150)
    span.set_attribute("gen_ai.usage.output_tokens", 45)
    
    # Set status
    span.set_status(StatusCode.OK)

# Export all spans to backend
tracer.export()
```

**Nested Spans (Traces):**
```python
tracer = Tracer(endpoint="http://localhost:8000", service_name="app")

with tracer.start_span("request", kind=SpanKind.SERVER) as parent:
    parent.set_attribute("http.method", "POST")
    parent.set_attribute("http.url", "/chat")
    
    # Child span (use parent's trace_id)
    with tracer.start_span("call_llm", parent_span_id=parent.span_id) as child:
        child.set_attribute("gen_ai.system", "anthropic")
        child.set_attribute("gen_ai.request.model", "claude-3-sonnet")

tracer.export()
```

**Error Handling:**
```python
from weft import StatusCode

try:
    with tracer.start_span("risky_operation") as span:
        # ... do something ...
        raise ValueError("Something went wrong")
except Exception as e:
    span.set_status(StatusCode.ERROR)
    span.set_attribute("error.message", str(e))
    raise
finally:
    tracer.export()
```

#### 3.2 OpenTelemetry Collector Integration

Send spans from any OTel SDK/Collector to Weft.

**OTel Collector config** (`collector-config.yaml`):
```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318

exporters:
  otlp:
    endpoint: http://weft-backend:8000
    headers:
      Authorization: "Bearer YOUR_TOKEN"  # if needed

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [otlp]
```

**Then from Python (using standard OTel SDK):**
```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

exporter = OTLPSpanExporter(endpoint="http://weft-backend:8000/v1/traces")
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(exporter))

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("my-span") as span:
    span.set_attribute("key", "value")
```

#### 3.3 Prompt Versioning & Labels

**Create a prompt:**
```bash
curl -X POST http://127.0.0.1:8000/prompts \
  -H "Content-Type: application/json" \
  -d '{"name":"customer-support"}'
```
Response: `{"id": "abc123", "name": "customer-support", ...}`

**Create a version:**
```bash
curl -X POST http://127.0.0.1:8000/prompts/abc123/versions \
  -H "Content-Type: application/json" \
  -d '{
    "template": "You are a customer support agent. Help the user: {{user_input}}",
    "config": {"temperature": 0.7, "max_tokens": 500}
  }'
```
Response: `{"id": "v1_xyz", "version_number": 1, ...}`

**Create a label (e.g., "production"):**
```bash
curl -X POST http://127.0.0.1:8000/prompts/abc123/labels \
  -H "Content-Type: application/json" \
  -d '{"name": "production", "version_id": "v1_xyz"}'
```

**Resolve prompt by label (SDK hot path):**
```bash
curl http://127.0.0.1:8000/prompts/customer-support/labels/production
```
Response: `{"template": "You are a customer support...", "config": {...}}`

#### 3.4 Datasets & Evaluation

**Create a dataset:**
```bash
curl -X POST http://127.0.0.1:8000/datasets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "customer-queries",
    "description": "Real customer support queries for evals"
  }'
```
Response: `{"id": "ds_123", ...}`

**Add items (promote trace as eval item):**
```bash
curl -X POST http://127.0.0.1:8000/datasets/ds_123/items \
  -H "Content-Type: application/json" \
  -d '{
    "source_trace_id": "deadbeefdeadbeefdeadbeefdeadbeef",
    "expected_output": {"answer": "Yes, we can help."}
  }'
```

**Run evaluator:**
```bash
curl -X POST http://127.0.0.1:8000/eval-runs \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "ds_123",
    "evaluator_name": "exact_match",
    "outputs": {
      "item_id_1": {"answer": "Yes, we can help."},
      "item_id_2": {"answer": "No, we cannot."}
    }
  }'
```

**Get eval results:**
```bash
curl http://127.0.0.1:8000/eval-runs/run_456
```
Response:
```json
{
  "id": "run_456",
  "status": "completed",
  "results": {
    "mean_score": 0.5,
    "item_count": 2,
    "items": [
      {"dataset_item_id": "...", "score": 1.0, "reasoning": "..."},
      {"dataset_item_id": "...", "score": 0.0, "reasoning": "..."}
    ]
  }
}
```

---

### Level 4: Advanced Configuration

#### 4.1 Custom Evaluators

Extend the evaluator interface for custom scoring logic:

```python
# backend/app/eval/custom_evaluator.py
from app.eval.evaluator import Evaluator, EvalResult
import re

class CustomEvaluator:
    name = "custom_pattern"
    
    def __init__(self, pattern: str, threshold: float = 0.8):
        self.pattern = re.compile(pattern)
        self.threshold = threshold
    
    def score(self, item: dict, output: str) -> EvalResult:
        matches = self.pattern.findall(str(output))
        score = min(1.0, len(matches) / (item.get("expected_count", 1)))
        return EvalResult(
            score=score,
            reasoning=f"Found {len(matches)} matches (expected {item.get('expected_count', 1)})"
        )
```

Register in `backend/app/api/eval_runs.py`:
```python
from app.eval.custom_evaluator import CustomEvaluator

def _build_evaluator(name: str, config: dict) -> Evaluator:
    # ... existing evaluators ...
    if name == "custom_pattern":
        return CustomEvaluator(pattern=config["pattern"], threshold=config.get("threshold", 0.8))
```

#### 4.2 Scaling: Multi-Instance Backend

For high-throughput scenarios:

1. **Shared Parquet Storage** (e.g., S3, NFS)
   ```python
   # backend/app/config.py
   DATA_DIR = Path(os.environ.get("WEFT_DATA_DIR", "s3://my-bucket/traces"))
   ```

2. **Distributed Query** (DuckDB queries S3 directly)
   ```python
   # backend/app/storage/query.py
   con = duckdb.connect(database=":memory:")
   con.install_extension("httpfs")
   con.load_extension("httpfs")
   rows = con.execute(f"SELECT * FROM read_parquet('s3://bucket/*.parquet')")
   ```

3. **Centralized Metadata DB** (PostgreSQL)
   ```python
   # All instances connect to same Postgres for prompts, datasets, evals
   DATABASE_URL = "postgresql://user:pass@db.example.com/weft"
   ```

#### 4.3 Backup & Recovery

**Daily Parquet backup:**
```bash
#!/bin/bash
BACKUP_DATE=$(date +%Y%m%d)
tar -czf weft-traces-$BACKUP_DATE.tar.gz $WEFT_DATA_DIR
aws s3 cp weft-traces-$BACKUP_DATE.tar.gz s3://my-backups/
```

**Database backup (PostgreSQL):**
```bash
pg_dump -h db.example.com -U weft_user weft_metadata | gzip > weft-metadata-$BACKUP_DATE.sql.gz
```

---

## API Reference

### Traces
- `GET /traces?limit=50` — list recent traces (summaries)
- `GET /traces/{trace_id}` — get all spans in a trace

### Prompts
- `GET /prompts` — list all prompts
- `POST /prompts` — create prompt (name required)
- `POST /prompts/{id}/versions` — create immutable version (template, config)
- `POST /prompts/{id}/labels` — create/update label (name, version_id)
- `GET /prompts/{name}/labels/{label}` — resolve label to version (SDK hot path)

### Datasets
- `GET /datasets` — list datasets
- `POST /datasets` — create dataset (name, description)
- `POST /datasets/{id}/items` — add item (input, expected_output, source_trace_id)

### Evaluators
- `POST /eval-runs` — run evaluator (dataset_id, evaluator_name, evaluator_config, outputs)
- `GET /eval-runs/{id}` — get results (status, results with mean_score, items)

Built-in evaluators:
- `exact_match` — 1.0 if output == expected_output
- `regex` — 1.0 if pattern matches output
- `schema_validity` — 1.0 if output dict has required_keys
- `llm_judge` — score via LLM (requires call_model callback)

---

## Troubleshooting

**"Connection refused" when sending traces**
- Check backend is running: `curl http://127.0.0.1:8000/healthz`
- Verify `WEFT_BACKEND_URL` matches backend address
- Check firewall/network policies

**Traces appear but don't query**
- Ensure `WEFT_DATA_DIR` has write permissions
- Check disk space: `df -h $WEFT_DATA_DIR`
- Verify DuckDB is not corrupted: `duckdb $WEFT_DATA_DIR/traces.db`

**Frontend shows "No data"**
- Check frontend backend URL: `echo $WEFT_BACKEND_URL`
- Verify CORS (if frontend != backend): check browser console for blocked requests

**Metadata DB errors**
- For PostgreSQL: `psql -h db -U weft_user -d weft_metadata -c "SELECT 1"`
- For SQLite: `ls -la $WEFT_DATA_DIR/weft.db`

---

## Development

### Running Tests

```bash
cd backend
pytest tests/
```

### Building Frontend for Production

```bash
cd frontend
npm run build
npm start
```

### Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit changes (`git commit -m "add my-feature"`)
4. Push and create a pull request

---

## Phases & Roadmap

- **Phase 0**: ✅ OTLP ingestion → Parquet → query
- **Phase 1**: ✅ Trace UI (waterfall view)
- **Phase 2**: ✅ Prompts, datasets, eval runner
- **Phase 3**: 🔄 RAG triad evaluators (TruLens-style retrieval/context/answer)
- **Phase 4**: 📅 Scale-out (ClickHouse upgrade path), optional JS/TS SDK

---

## License

MIT

## Support

- **Issues**: [GitHub Issues](https://github.com/somesh-ghaturle/weft/issues)
- **Discussions**: [GitHub Discussions](https://github.com/somesh-ghaturle/weft/discussions)
- **Email**: [contact@weft.dev](mailto:contact@weft.dev) (future)
