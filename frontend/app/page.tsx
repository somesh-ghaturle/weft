import Link from "next/link";
import { listTraces } from "./lib/api";

function formatStart(ns: number): string {
  return new Date(ns / 1_000_000).toLocaleString();
}

export default async function TracesPage() {
  const traces = await listTraces();

  return (
    <main style={{ padding: "2rem", maxWidth: 1000, margin: "0 auto" }}>
      <h1>Traces</h1>
      {traces.length === 0 ? (
        <p>No traces yet. Send some spans to /v1/traces.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
              <th style={{ padding: "0.5rem" }}>Trace ID</th>
              <th style={{ padding: "0.5rem" }}>Started</th>
              <th style={{ padding: "0.5rem" }}>Spans</th>
              <th style={{ padding: "0.5rem" }}>Duration</th>
              <th style={{ padding: "0.5rem" }}>Models</th>
              <th style={{ padding: "0.5rem" }}>Tokens (in/out)</th>
            </tr>
          </thead>
          <tbody>
            {traces.map((t) => (
              <tr key={t.trace_id} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "0.5rem", fontFamily: "monospace" }}>
                  <Link href={`/traces/${t.trace_id}`}>{t.trace_id.slice(0, 12)}…</Link>
                </td>
                <td style={{ padding: "0.5rem" }}>{formatStart(t.trace_start_ns)}</td>
                <td style={{ padding: "0.5rem" }}>{t.span_count}</td>
                <td style={{ padding: "0.5rem" }}>{t.total_duration_ms.toFixed(1)} ms</td>
                <td style={{ padding: "0.5rem" }}>
                  {t.models.filter(Boolean).join(", ") || "—"}
                </td>
                <td style={{ padding: "0.5rem" }}>
                  {t.total_input_tokens} / {t.total_output_tokens}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
