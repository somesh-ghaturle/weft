# UI Context

## Theme

The UI should feel lightweight, technical, and focused on observability work. The current implementation favors a simple, readable experience over a polished design system, with clear structure for tables, traces, and metadata views.

## Colors

Use CSS variables for consistency and avoid hardcoded hex values in components.

| Role | CSS Variable | Value |
| --- | --- | --- |
| Page background | --bg-base | #0b1020 |
| Surface | --bg-surface | #111827 |
| Primary text | --text-primary | #f9fafb |
| Muted text | --text-muted | #9ca3af |
| Primary accent | --accent-primary | #3b82f6 |
| Border | --border-default | #374151 |
| Error | --state-error | #ef4444 |
| Success | --state-success | #10b981 |

## Typography

| Role | Font | Variable |
| --- | --- | --- |
| UI text | Inter, system sans | --font-sans |
| Code/mono | JetBrains Mono, monospace | --font-mono |

## Border Radius

| Context | Class |
| --- | --- |
| Inline / small UI | rounded-sm |
| Cards / panels | rounded-md |
| Modals / overlays | rounded-lg |

## Component Library

The frontend currently uses a minimal approach with direct React and Next.js components rather than a large component framework. Keep the implementation approachable and avoid introducing unnecessary UI abstraction until the product direction is clearer.

## Layout Patterns

- Trace list pages should present data in a compact tabular layout with clear columns.
- Trace detail pages should use a vertical waterfall-style layout with strong hierarchy and readable metadata.
- Detail and list views should remain focused and avoid excessive visual noise.

## Icons

Use simple, stroke-based icons consistently and keep icon usage minimal and purposeful.
