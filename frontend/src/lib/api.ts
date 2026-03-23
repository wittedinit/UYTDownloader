const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Types ─────────────────────────────────────────────────────────────

export interface Source {
  id: string;
  type: string;
  canonical_url: string;
  external_id: string;
  title: string | null;
  uploader: string | null;
  thumbnail_url: string | null;
  entry_count: number;
  last_scanned_at: string | null;
  created_at: string;
}

export interface Entry {
  id: string;
  external_video_id: string;
  title: string;
  duration: number | null;
  upload_date: string | null;
  thumbnail_url: string | null;
  availability: string;
  created_at: string;
}

export interface EntryDetail extends Entry {
  metadata_json: Record<string, unknown> | null;
  format_snapshot: FormatSnapshot | null;
}

export interface FormatSnapshot {
  id: string;
  fetched_at: string;
  expires_at: string;
  formats_json: Record<string, unknown>[];
  subtitles_json: Record<string, unknown> | null;
  chapters_json: Record<string, unknown>[] | null;
}

export interface Job {
  id: string;
  kind: string;
  status: string;
  priority: number;
  progress_pct: number;
  speed_bps: number | null;
  eta_seconds: number | null;
  error_code: string | null;
  error_message: string | null;
  entry_id: string | null;
  entry_title: string | null;
  entry_thumbnail: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobStage {
  id: string;
  type: string;
  status: string;
  order: number;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

export interface Artifact {
  id: string;
  kind: string;
  filename: string;
  size_bytes: number | null;
  duration: number | null;
  mime_type: string | null;
  created_at: string;
}

export interface JobDetail extends Job {
  stages: JobStage[];
  artifacts: Artifact[];
  request: {
    format_mode: string;
    format_spec: string;
    container: string;
    max_height: number | null;
    sponsorblock_action: string;
    output_dir: string | null;
  } | null;
}

// ── Probe ─────────────────────────────────────────────────────────────

export async function submitProbe(url: string) {
  return apiFetch<{ probe_id: string; status: string }>("/api/probe", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function pollProbe(probeId: string) {
  return apiFetch<{
    status: string;
    probe_id: string;
    source?: Source & { entries?: Entry[] };
    format_snapshot?: FormatSnapshot;
    error?: string;
  }>(`/api/probe/${probeId}`);
}

// ── Sources & Entries ─────────────────────────────────────────────────

export async function listSources(params?: { type?: string; search?: string; page?: number }) {
  const q = new URLSearchParams();
  if (params?.type) q.set("type", params.type);
  if (params?.search) q.set("search", params.search);
  if (params?.page) q.set("page", String(params.page));
  return apiFetch<{ sources: Source[]; total: number }>(`/api/sources?${q}`);
}

export async function getSourceEntries(sourceId: string, page = 1) {
  return apiFetch<{ entries: Entry[]; total: number; page: number; per_page: number }>(
    `/api/sources/${sourceId}/entries?page=${page}&per_page=50`
  );
}

export async function getEntry(entryId: string) {
  return apiFetch<EntryDetail>(`/api/entries/${entryId}`);
}

// ── Jobs ──────────────────────────────────────────────────────────────

export async function createJobs(params: {
  entry_ids: string[];
  format_mode?: string;
  quality?: string;
  sponsorblock_action?: string;
}) {
  return apiFetch<{ jobs: Job[] }>("/api/jobs", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function listJobs(params?: { status?: string; page?: number }) {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.page) q.set("page", String(params.page));
  return apiFetch<{ jobs: Job[]; total: number; page: number; per_page: number }>(
    `/api/jobs?${q}`
  );
}

export async function getJob(jobId: string) {
  return apiFetch<JobDetail>(`/api/jobs/${jobId}`);
}

export async function cancelJob(jobId: string) {
  return apiFetch<Job>(`/api/jobs/${jobId}/cancel`, { method: "POST" });
}

export async function retryJob(jobId: string) {
  return apiFetch<Job>(`/api/jobs/${jobId}/retry`, { method: "POST" });
}

// ── Health ────────────────────────────────────────────────────────────

export async function getHealth() {
  return apiFetch<Record<string, unknown>>("/health");
}
