export function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    // OrbStack local dev: route to backend container via .orb.local DNS
    if (window.location.hostname.endsWith(".orb.local")) {
      return "http://uyt-backend-1.orb.local:8000";
    }
    // Production/Unraid: backend on same host, port 8000
    // Works with IP, hostname, or domain — just swap the port
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

const API_BASE = resolveApiBase();

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
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
  current_stage: string | null;
  completed_stages: number;
  total_stages: number;
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
  download_url: string | null;
  file_exists: boolean;
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
    source?: Source;
    entries?: Entry[];
    entry_count?: number;
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
  embed_subtitles?: boolean;
  normalize_audio?: boolean;
  playback_speed?: number;
  output_format?: string;
  video_bitrate?: string;
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

export async function deleteJob(jobId: string) {
  return apiFetch<void>(`/api/jobs/${jobId}`, { method: "DELETE" });
}

export async function bulkDeleteJobs(jobIds: string[]) {
  return apiFetch<{ deleted: number; skipped: number }>("/api/jobs/bulk-delete", {
    method: "POST",
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export async function bulkRetryJobs(jobIds: string[]) {
  return apiFetch<{ retried: number; skipped: number }>("/api/jobs/bulk-retry", {
    method: "POST",
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

// ── Subscriptions ─────────────────────────────────────────────────────

export interface Subscription {
  id: string;
  source_id: string;
  enabled: boolean;
  check_interval_minutes: number;
  last_checked_at: string | null;
  next_check_at: string | null;
  auto_download: boolean;
  format_mode: string;
  quality: string;
  sponsorblock_action: string;
  source_title: string | null;
  source_type: string | null;
  entry_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionFilter {
  id: string;
  filter_type: string;
  value: string | null;
  enabled: boolean;
}

export interface SubscriptionDetail extends Subscription {
  filters: SubscriptionFilter[];
}

export async function listSubscriptions() {
  return apiFetch<{ subscriptions: Subscription[]; total: number }>("/api/subscriptions");
}

export async function createSubscription(params: {
  source_id: string;
  check_interval_minutes?: number;
  auto_download?: boolean;
  format_mode?: string;
  quality?: string;
  sponsorblock_action?: string;
  filters?: { filter_type: string; value?: string; enabled?: boolean }[];
}) {
  return apiFetch<SubscriptionDetail>("/api/subscriptions", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function deleteSubscription(subId: string) {
  return apiFetch<void>(`/api/subscriptions/${subId}`, { method: "DELETE" });
}

export async function triggerSubscriptionCheck(subId: string) {
  return apiFetch<{ task_id: string; status: string }>(
    `/api/subscriptions/${subId}/check`,
    { method: "POST" }
  );
}

export async function updateSubscription(subId: string, updates: Record<string, unknown>) {
  return apiFetch<Subscription>(`/api/subscriptions/${subId}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

// ── Compilations ──────────────────────────────────────────────────────

export async function createCompilation(params: {
  items: { entry_id: string; position: number }[];
  mode?: string;
  title?: string;
  normalize_audio?: boolean;
}) {
  return apiFetch<{ job_id: string; status: string; item_count: number }>("/api/compilations", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// ── Library ───────────────────────────────────────────────────────────

export interface LibraryFile {
  filename: string;
  size_bytes: number;
  modified_at: number;
  download_url: string;
  extension: string;
}

export async function listLibraryFiles(opts: { page?: number; search?: string; sort?: string; file_type?: string } = {}) {
  const { page = 1, search = "", sort = "date_desc", file_type = "all" } = opts;
  const params = new URLSearchParams({ page: String(page), per_page: "200", sort, file_type });
  if (search) params.set("search", search);
  return apiFetch<{ files: LibraryFile[]; total: number; page: number; per_page: number }>(
    `/api/library?${params}`
  );
}

export async function deleteLibraryFile(filename: string) {
  return apiFetch<void>(`/api/library/${encodeURIComponent(filename)}`, { method: "DELETE" });
}

export async function createZip(params: { filenames: string[]; zip_name?: string }) {
  return apiFetch<{ filename: string; size_bytes: number; download_url: string; file_count: number }>(
    "/api/library/zip",
    { method: "POST", body: JSON.stringify(params) }
  );
}

export async function deleteZip(filename: string) {
  return apiFetch<void>(`/api/library/zip/${encodeURIComponent(filename)}`, { method: "DELETE" });
}

export async function mergeLibraryFiles(params: {
  filenames: string[];
  title?: string;
  mode?: string;
  normalize_audio?: boolean;
}) {
  return apiFetch<{ task_id: string; status: string; output_filename: string }>("/api/library/merge", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getMergeStatus(taskId: string) {
  return apiFetch<{
    task_id: string;
    status: string;
    progress?: number;
    stage?: string;
    filename?: string;
    size_bytes?: number;
    chapters?: number;
    error?: string;
  }>(`/api/library/merge/${taskId}`);
}

// ── Storage Management ────────────────────────────────────────────────

export interface DiskUsage {
  disk_total_gb: number;
  disk_used_gb: number;
  disk_free_gb: number;
  disk_free_pct: number;
  downloads_bytes: number;
  downloads_gb: number;
  downloads_file_count: number;
}

export async function getDiskUsage() {
  return apiFetch<DiskUsage>("/api/storage/usage");
}

export async function getStoragePresets() {
  return apiFetch<{
    retention_presets: { key: string; label: string; is_forever: boolean }[];
    cleanup_strategies: { key: string; description: string }[];
  }>("/api/storage/presets");
}

export async function runRetention(retention: string, dryRun = false) {
  return apiFetch<Record<string, unknown>>(
    `/api/storage/retention?retention=${retention}&dry_run=${dryRun}`,
    { method: "POST" }
  );
}

export async function runDiskGuard(minFreePct: number, strategy: string, dryRun = false) {
  return apiFetch<Record<string, unknown>>(
    `/api/storage/disk-guard?min_free_pct=${minFreePct}&strategy=${strategy}&dry_run=${dryRun}`,
    { method: "POST" }
  );
}

// ── Concurrency Mode ──────────────────────────────────────────────────

export interface ConcurrencyModeInfo {
  mode: string;
  available_modes: { key: string; label: string; description: string }[];
  active_profile: {
    fragment_concurrency: number;
    request_sleep: number;
    download_sleep: number;
    max_sleep: number;
    throttle_detection_bps: number;
    retries: number;
    fragment_retries: number;
  };
}

export async function getConcurrencyMode() {
  return apiFetch<ConcurrencyModeInfo>("/api/storage/concurrency-mode");
}

export async function setConcurrencyMode(mode: string) {
  return apiFetch<{ mode: string }>("/api/storage/concurrency-mode", {
    method: "PUT",
    body: JSON.stringify({ mode }),
  });
}

// ── Health ────────────────────────────────────────────────────────────

export async function getHealth() {
  return apiFetch<Record<string, unknown>>("/health");
}
