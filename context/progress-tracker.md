# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- MVP stabilization and polish

## Current Goal

- Keep the core self-hosted tracing and evaluation workflow working end to end while preserving the current architecture.

## Completed

- Added a dedicated context folder at the repository root.
- Implemented OTLP ingestion and trace storage through the FastAPI backend.
- Built trace listing and trace detail endpoints backed by parquet and DuckDB queries.
- Added prompt versioning, labeling, and prompt resolution endpoints.
- Added dataset and dataset-item creation flows, including trace-based item creation.
- Added eval run creation and result retrieval flows with built-in evaluators.
- Built a simple Next.js trace explorer with a waterfall-style detail view.

## In Progress

- UI polish and simplification around the trace experience.
- Documentation and contributor context updates to reflect current milestones.

## Next Up

- Add stronger validation and error handling around the metadata and eval flows.
- Improve frontend usability for prompts, datasets, and eval runs.
- Add tests and more operational guidance for self-hosted usage.

## Open Questions

- Whether authentication and multi-user access should be introduced in a later phase.
- Whether retention, partitioning, and larger-scale storage improvements should be prioritized next.

## Architecture Decisions

- The current implementation keeps trace storage and metadata storage separate to preserve a simple architecture and avoid over-committing to a single database model.
- The frontend remains thin and reads from the backend API rather than bypassing the service layer.

## Session Notes

- The repository is now centered on a practical MVP: ingest traces, explore them, manage prompts/datasets/evals, and keep the setup self-hosted and lightweight.
