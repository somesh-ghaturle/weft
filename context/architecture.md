# Architecture Context

## Stack

| Layer | Technology | Role |
| --- | --- | --- |
| Backend API | FastAPI | Exposes ingestion and management endpoints |
| Frontend | Next.js + React | Browses traces, prompts, datasets, and eval runs |
| Trace ingestion | OTLP over HTTP | Accepts traces from any OTel-compatible client |
| Storage | DuckDB + Parquet | Stores span data and supports trace aggregation |
| Metadata | SQLAlchemy + SQLite/Postgres | Stores prompt versions, labels, datasets, and eval runs |
| SDK | Python package | Allows applications to emit traces to Weft |

## Current Implementation Status

### Completed work

- OTLP ingestion endpoint at /v1/traces.
- Background span writer that batches and flushes spans to parquet files.
- Trace listing and trace detail query endpoints.
- Prompt CRUD and label/version management endpoints.
- Dataset creation and trace-based item creation endpoints.
- Eval run creation and result retrieval endpoints.
- A simple Next.js trace explorer with a waterfall-style detail view.

### Current phase

- MVP stabilization and polish.
- Keep the architecture simple and self-hosted rather than adding infrastructure complexity.

## System Boundaries

- backend/app/api/ — HTTP routes for traces, prompts, datasets, and eval runs.
- backend/app/ingestion/ — OTLP request parsing and ingestion entry points.
- backend/app/storage/ — Span writing, parquet persistence, and query execution.
- backend/app/metadata/ — Metadata models and persistence for prompts, datasets, and eval runs.
- backend/app/eval/ — Evaluator implementations and eval execution logic.
- frontend/app/ — Next.js UI for browsing traces and related resources.
- sdk/python/ — Python SDK used by applications to send traces to Weft.

## Storage Model

- SQLite/Postgres metadata DB: stores prompt versions, labels, datasets, eval runs, and related metadata.
- Parquet files in backend/data: store span data and trace records in a columnar format for efficient queries.

## Auth and Access Model

- Weft is currently self-hosted and does not implement multi-tenant authentication.
- Access is assumed to be local or environment-controlled by the deployment context.
- Mutations are handled through the backend API and should be validated at the route boundary.

## Invariants

1. OTLP ingestion remains vendor-neutral and accepts standard OTel payloads.
2. Trace data is written through the background writer rather than directly from request handlers.
3. Metadata and span storage remain logically separate so trace data and application metadata can evolve independently.
4. The frontend must read from backend API endpoints rather than bypassing the service layer.
5. New features should preserve the project’s simple, self-hosted operating model.
