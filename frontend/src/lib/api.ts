export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type VerdictKey =
  | "reproduced"
  | "needs_human"
  | "not_reproduced"
  | "needs_info"
  | "duplicate"
  | "already_fixed"
  | "fabricated";

export type Card = {
  id: string;
  seq: number;
  title: string;
  reporter: string;
  channel: string;
  is_test_data: boolean;
  received_at: number;
  status: "queued" | "processing" | "patching" | "done" | "error";
  stage: string | null;
  verdict: VerdictKey | null;
  verdict_label: string | null;
  verdict_rule: string | null;
  version: string | null;
  functions: string[];
  bug_class: string | null;
  injection: boolean;
  false_claims: number;
  patch_status: string | null;
  sandbox_used: boolean;
};

export type Stats = {
  total: number;
  decided: number;
  by_verdict: Record<VerdictKey, number>;
  in_progress: number;
  patches_ready: number;
  sandboxes_started: number;
  hours_saved: number;
  hours_assumption: string;
  model_calls: number;
  fallback_steps: number;
  tokens: number;
  cost_usd: number;
};

export type Check = {
  kind: string;
  claim: string;
  status: "verified" | "false" | "moved" | "unverifiable";
  detail: string;
  command: string;
  hard_falsehood: boolean;
};

export type Sanitizer = {
  tool: string;
  kind: string;
  summary: string;
  frames: { function: string; file: string; line: number }[];
  top_function: string | null;
};

export type Reproduction = {
  error?: string;
  run_id: string;
  backend: string;
  ref: string;
  image: string;
  container_command: string;
  isolation: string[];
  attachments: string[];
  script: string;
  script_source: string;
  build_ok: boolean;
  build_log: string;
  attempts: { attempt: number; exit_code: number; output: string; sanitizer: Sanitizer | null }[];
  timed_out: boolean;
  duration_s: number;
};

export type PatchCheck = { pass: boolean; detail: string };

export type PatchAttempt = {
  n: number;
  source: string;
  rationale?: string;
  diff?: string;
  test_diff?: string;
  changed_lines?: number;
  anticheat?: { rule: string; detail: string }[];
  checks?: Record<string, PatchCheck>;
  outcome: "rejected" | "failed" | "passed" | "stopped";
  failure?: string;
  feedback?: string;
  feedback_source?: string;
  sandbox_run?: string;
  duration_s?: number;
  logs?: Record<string, string>;
};

export type Patch = {
  status: "queued" | "running" | "fixed" | "could_not_fix" | "error";
  reason?: string;
  function?: string;
  editable_files?: string[];
  max_attempts?: number;
  max_changed_lines?: number;
  root_cause?: { root_cause: string; faulty_lines: number[]; fix_strategy: string; source: string };
  attempts?: PatchAttempt[];
  final_diff?: string;
  final_test?: string;
  test_path?: string;
};

export type Advisory = {
  status: string;
  sent: boolean;
  visibility: string;
  steps: { call: string; body: string }[];
  payload: {
    summary: string;
    description: string;
    cwe_ids: string[];
    severity: string;
    vulnerabilities: Record<string, unknown>[];
  };
  error?: string;
  html_url?: string;
  ghsa_id?: string;
};

export type ModelCall = {
  id: number;
  stage: string;
  tier: string;
  model: string;
  provider: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost_usd: number;
  ok: number;
  error: string | null;
};

export type Evidence = {
  timings?: Record<string, number>;
  injection?: { kind: string; excerpt: string }[];
  claims_source?: string;
  claims?: Record<string, unknown>;
  grounding?: { resolved_version: string | null; version_note: string; checks: Check[]; fixed_in: Record<string, string> | null };
  cves?: { cve_id: string; status: string; detail: string; source: string }[];
  web?: { query: string; status: string; note?: string; results: { title: string; url: string; snippet: string }[] }[];
  duplicate?: { of: string; title: string; score: number; parts: Record<string, number>; how: string } | null;
  plan?: { runnable: boolean; script: string; source: string; reason: string };
  reproduction?: Reproduction;
  match?: { ok: boolean; detail: string } | null;
  sandbox_skipped?: string;
  explanation_source?: string;
};

export type ReportDetail = {
  id: string;
  title: string;
  body: string;
  reporter: string;
  channel: string;
  attachments: Record<string, string>;
  is_test_data: boolean;
  received_at: number;
  status: Card["status"];
  stage: string | null;
  verdict: VerdictKey | null;
  verdict_rule: string | null;
  summary: string | null;
  reply: string | null;
  evidence: Evidence;
  patch: Patch | null;
  advisory: Advisory | null;
  decision: { action: string; note: string; at: number } | null;
  card: Card;
  model_calls: ModelCall[];
};

export type Health = {
  models: { live: boolean; provider: string; base_url: string; tiers: Record<string, string> };
  tavily: boolean;
  cve_lookup: boolean;
  sandbox: { ok: boolean; backend: string; detail: string; image: string };
  github: boolean;
  budget: { daily_usd: number; spent_24h_usd: number };
  project: { name: string; tags: string[]; fictional: boolean };
};

export class ApiError extends Error {}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(`Can't reach the Bouncer API at ${API_URL}. Start it with \`make api\` and reload.`);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new ApiError(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => call<Health>("/api/health"),
  reports: () => call<{ reports: Card[]; stats: Stats }>("/api/reports"),
  report: (id: string) => call<ReportDetail>(`/api/reports/${encodeURIComponent(id)}`),
  submit: (body: { title: string; body: string; reporter: string; attachments: Record<string, string> }) =>
    call<{ id: string }>("/api/reports", { method: "POST", body: JSON.stringify(body) }),
  loadDemo: () => call<{ ids: string[] }>("/api/demo/load", { method: "POST" }),
  reset: () => call<{ ok: boolean }>("/api/demo/reset", { method: "POST" }),
  decide: (id: string, action: string, note = "") =>
    call(`/api/reports/${encodeURIComponent(id)}/decision`, { method: "POST", body: JSON.stringify({ action, note }) }),
  publishAdvisory: (id: string) =>
    call<Advisory>(`/api/reports/${encodeURIComponent(id)}/advisory/publish`, { method: "POST" }),
};
