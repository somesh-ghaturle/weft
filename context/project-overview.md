# Weft

## Overview

Weft is a self-hosted observability platform for LLM applications that brings traces, evals, and prompts together in one lightweight system. It is built to be simple to run locally while still supporting practical workflows for debugging and evaluation.

## Current Goals

1. Accept trace data from standard OpenTelemetry clients without vendor lock-in.
2. Store and query traces efficiently using a simple self-hosted architecture.
3. Provide a lightweight UI for exploring traces, prompts, datasets, and eval results.
4. Keep the project approachable for small teams and local development.

## Core User Flow

1. A Python application or OTel SDK sends traces to the backend.
2. The backend ingests the OTLP payload and stores the spans.
3. The frontend loads trace and metadata views from the backend API.
4. Users inspect traces and manage prompts, datasets, and evals in one place.

## Current Features

### Trace Observability

- Ingest OTLP traces from any OTel-compatible source.
- Aggregate traces and inspect span-level details through a waterfall-style UI.

### Prompt and Dataset Management

- Track prompt versions and labels.
- Create datasets and add items derived from traces.

### Evaluation Support

- Create eval runs against datasets with built-in evaluators such as exact match, regex, and schema validity.

## Current Scope

### In Scope

- Backend ingestion and storage for traces.
- Metadata management for prompts, datasets, and eval runs.
- A Next.js-based frontend for browsing trace data and related resources.

### Out of Scope

- Advanced multi-tenant authentication.
- Large-scale enterprise observability features beyond the current self-hosted scope.

## Success Criteria

1. A user can send an OTLP trace to the backend and see it represented in the UI.
2. Prompt and dataset metadata can be created and viewed through the backend API.
3. The project remains simple to run locally without requiring a heavy infrastructure stack.
4. The core workflow is understandable to a new contributor from the repository docs and context files.
