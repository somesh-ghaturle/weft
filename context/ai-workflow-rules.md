# AI Workflow Rules

## Approach

Weft is currently in an MVP-focused phase. Implementation should preserve the existing architecture: OTLP ingestion and trace storage first, then metadata and evaluation functionality, with the frontend reflecting the backend’s capabilities.

## Scoping Rules

- Work on one feature unit at a time.
- Prefer small, verifiable increments over broad speculative changes.
- Keep backend, frontend, and SDK changes aligned with the same feature slice.

## Current Project Phases

### Phase 1 — Core ingestion and storage

- OTLP trace ingestion through FastAPI.
- Background writer and parquet-backed trace storage.
- Trace listing and trace detail query endpoints.

### Phase 2 — Metadata and evaluation workflows

- Prompt versioning and label resolution.
- Dataset creation and dataset item creation from traces.
- Eval run creation and scoring workflows.

### Phase 3 — Lightweight UX and polish

- Trace browsing and waterfall-style detail views.
- Simple navigation and readable data presentation.
- Continued stabilization of the self-hosted experience.

## When to Split Work

Split an implementation step if it combines:

- UI changes and storage or ingestion changes.
- Multiple unrelated API routes or modules.
- Behavior not clearly defined in the context files.

If a change cannot be verified end to end quickly, the scope is too broad and should be split.

## Handling Missing Requirements

- Do not invent product behavior not defined in the context files.
- If a requirement is ambiguous, resolve it in the relevant context file before implementing.
- If a requirement is missing, add it as an open question in progress-tracker.md before continuing.

## Protected Files

Do not modify the following unless explicitly instructed:

- Core ingestion and storage contracts that define the backend’s public behavior.
- Third-party or generated internals.

## Keeping Docs in Sync

Update the relevant context file whenever implementation changes:

- System architecture or boundaries.
- Storage model decisions.
- Code conventions or standards.
- Feature scope or current completion status.

## Before Moving to the Next Unit

1. The current unit works end to end within its defined scope.
2. No invariant defined in architecture.md was violated.
3. progress-tracker.md reflects the completed work.
4. The relevant backend/frontend checks pass.
