export interface TraceSummary {
  trace_id: string;
  span_count: number;
  trace_start_ns: number;
  trace_end_ns: number;
  total_duration_ms: number;
  total_input_tokens: number;
  total_output_tokens: number;
  models: string[];
}

export interface Span {
  trace_id: string;
  span_id: string;
  parent_span_id: string;
  name: string;
  kind: string;
  start_time_unix_nano: number;
  end_time_unix_nano: number;
  duration_ms: number;
  status_code: string;
  service_name: string;
  gen_ai_system: string;
  gen_ai_request_model: string;
  gen_ai_usage_input_tokens: number;
  gen_ai_usage_output_tokens: number;
  attributes_json: string;
}

async function backendFetch<T>(path: string): Promise<T> {
  const res = await fetch(`/backend${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`weft backend request failed: ${res.status} ${path}`);
  }
  return res.json() as Promise<T>;
}

export function listTraces(limit = 50): Promise<TraceSummary[]> {
  return backendFetch<TraceSummary[]>(`/traces?limit=${limit}`);
}

export function getTrace(traceId: string): Promise<Span[]> {
  return backendFetch<Span[]>(`/traces/${traceId}`);
}
