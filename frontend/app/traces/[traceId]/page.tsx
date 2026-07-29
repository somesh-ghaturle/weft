import { getTrace, type Span } from "../../lib/api";

const KIND_COLORS: Record<string, string> = {
  server: "#4f8cff",
  client: "#22a06b",
  internal: "#9b59b6",
  producer: "#e6a817",
  consumer: "#e67e22",
  unspecified: "#999",
};

function buildTree(spans: Span[]): Map<string, Span[]> {
  const children = new Map<string, Span[]>();
  for (const span of spans) {
    const key = span.parent_span_id || "";
    if (!children.has(key)) children.set(key, []);
    children.get(key)!.push(span);
  }
  return children;
}

function WaterfallRow({
  span,
  depth,
  traceStart,
  traceDuration,
  children,
}: {
  span: Span;
  depth: number;
  traceStart: number;
  traceDuration: number;
  children: React.ReactNode;
}) {
  const offsetPct = traceDuration > 0 ? ((span.start_time_unix_nano - traceStart) / traceDuration) * 100 : 0;
  const widthPct = traceDuration > 0 ? Math.max((span.duration_ms * 1_000_000) / traceDuration * 100, 0.5) : 100;
  const color = KIND_COLORS[span.kind] ?? KIND_COLORS.unspecified;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", padding: "0.35rem 0" }}>
        <div style={{ width: 280, paddingLeft: depth * 16, display: "flex", gap: "0.4rem", alignItems: "center" }}>
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: color,
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: "0.85rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {span.name}
          </span>
        </div>
        <div style={{ flex: 1, position: "relative", height: 18, background: "#f2f2f2" }}>
          <div
            title={`${span.duration_ms.toFixed(2)} ms`}
            style={{
              position: "absolute",
              left: `${offsetPct}%`,
              width: `${widthPct}%`,
              height: "100%",
              background: color,
              borderRadius: 2,
            }}
          />
        </div>
        <div style={{ width: 90, textAlign: "right", fontSize: "0.8rem", color: "#555" }}>
          {span.duration_ms.toFixed(1)} ms
        </div>
        {span.status_code === "STATUS_CODE_ERROR" && (
          <span style={{ marginLeft: "0.5rem", color: "#c0392b", fontSize: "0.75rem" }}>ERROR</span>
        )}
      </div>
      {children}
    </div>
  );
}

function renderTree(
  parentId: string,
  tree: Map<string, Span[]>,
  depth: number,
  traceStart: number,
  traceDuration: number
): React.ReactNode {
  const spans = tree.get(parentId) ?? [];
  return spans.map((span) => (
    <WaterfallRow key={span.span_id} span={span} depth={depth} traceStart={traceStart} traceDuration={traceDuration}>
      {renderTree(span.span_id, tree, depth + 1, traceStart, traceDuration)}
    </WaterfallRow>
  ));
}

export default async function TraceDetailPage({
  params,
}: {
  params: Promise<{ traceId: string }>;
}) {
  const { traceId } = await params;
  const spans = await getTrace(traceId);

  if (spans.length === 0) {
    return (
      <main style={{ padding: "2rem" }}>
        <p>Trace not found.</p>
      </main>
    );
  }

  const traceStart = Math.min(...spans.map((s) => s.start_time_unix_nano));
  const traceEnd = Math.max(...spans.map((s) => s.end_time_unix_nano));
  const traceDuration = traceEnd - traceStart;
  const tree = buildTree(spans);

  const totalInputTokens = spans.reduce((sum, s) => sum + s.gen_ai_usage_input_tokens, 0);
  const totalOutputTokens = spans.reduce((sum, s) => sum + s.gen_ai_usage_output_tokens, 0);

  return (
    <main style={{ padding: "2rem", maxWidth: 1100, margin: "0 auto" }}>
      <a href="/">&larr; All traces</a>
      <h1 style={{ fontFamily: "monospace", fontSize: "1.1rem" }}>{traceId}</h1>
      <p style={{ color: "#555" }}>
        {spans.length} spans · {(traceDuration / 1_000_000).toFixed(1)} ms total ·{" "}
        {totalInputTokens}/{totalOutputTokens} tokens (in/out)
      </p>
      <div style={{ marginTop: "1.5rem" }}>{renderTree("", tree, 0, traceStart, traceDuration)}</div>
    </main>
  );
}
