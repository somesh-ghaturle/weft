# Code Standards

## General

- Keep modules small and focused on a single responsibility.
- Fix root causes instead of layering workarounds.
- Keep backend and frontend changes scoped to the relevant concern.
- Favor simple, maintainable patterns over introducing new infrastructure.

## Python

- Prefer clear, explicit functions and small data transfer objects.
- Keep ingestion and storage logic predictable and easy to reason about.
- Validate external input at API boundaries before using it.
- Keep FastAPI routers thin and delegate logic to dedicated modules where possible.

## TypeScript / Next.js

- Use TypeScript strictly and prefer explicit interfaces for data shapes.
- Keep React components focused and composable.
- Use server-safe patterns by default and only introduce client-side behavior when needed.
- Keep the UI simple and readable rather than over-engineered.

## Styling

- Use the existing design language rather than introducing ad-hoc visual patterns.
- Favor simple layout and readability over decorative complexity.
- Keep inline styles minimal unless a broader styling system is introduced intentionally.

## API Routes

- Validate request input before executing business logic.
- Return consistent response shapes for successful and failed operations.
- Keep route logic thin and delegate work to dedicated modules.
- Preserve the existing route structure under backend/app/api/.

## Data and Storage

- Keep metadata in the metadata database.
- Keep large trace payloads in parquet-backed storage.
- Avoid storing large generated content directly in the metadata database.
- Keep trace and metadata concerns separated by design.

## File Organization

- backend/app/api/ — API route modules.
- backend/app/ingestion/ — ingestion and protocol handling.
- backend/app/storage/ — persistence and query helpers.
- backend/app/metadata/ — SQLAlchemy models and data access.
- backend/app/eval/ — evaluator implementations and execution helpers.
- frontend/app/ — Next.js pages and route-level UI.
- sdk/python/ — Python SDK entry points and tracing helpers.
