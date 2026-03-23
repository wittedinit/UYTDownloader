"use client";

import { useState, useEffect, useCallback } from "react";
import { listJobs, cancelJob, retryJob, getJob, bulkDeleteJobs, deleteJob, type Job, type JobDetail } from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-500/10 text-slate-400",
  queued: "bg-amber-500/10 text-amber-400",
  running: "bg-blue-500/10 text-blue-400",
  completed: "bg-emerald-500/10 text-emerald-400",
  failed: "bg-red-500/10 text-red-400",
  cancelled: "bg-slate-500/10 text-slate-500",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggleJob = (id: string) => setSelected((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const toggleAll = () => { if (selected.size === jobs.length) setSelected(new Set()); else setSelected(new Set(jobs.map((j) => j.id))); };

  const handleBulkDelete = async () => {
    if (!confirm(`Delete ${selected.size} job${selected.size !== 1 ? "s" : ""} from history?`)) return;
    try { await bulkDeleteJobs(Array.from(selected)); setSelected(new Set()); fetchJobs(); } catch {}
  };

  const handleDeleteOne = async (id: string) => {
    try { await deleteJob(id); setSelected((p) => { const n = new Set(p); n.delete(id); return n; }); fetchJobs(); } catch {}
  };

  const fetchJobs = useCallback(async () => {
    try {
      const res = await listJobs({ status: filter || undefined });
      setJobs(res.jobs);
      setTotal(res.total);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, [filter]);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const handleCancel = async (jobId: string) => { try { await cancelJob(jobId); fetchJobs(); } catch {} };
  const handleRetry = async (jobId: string) => { try { await retryJob(jobId); fetchJobs(); } catch {} };
  const showDetail = async (jobId: string) => { try { setDetail(await getJob(jobId)); } catch {} };

  const formatBytes = (bytes: number | null) => {
    if (!bytes) return "-";
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Jobs</h1>
        <p className="text-sm text-[var(--muted)]">Monitor download progress and manage queued jobs</p>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-6">
        {["", "queued", "running", "completed", "failed"].map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              filter === s
                ? "bg-indigo-600 text-white"
                : "bg-[var(--card)] border border-[var(--card-border)] text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--muted)]"
            }`}
          >
            {s || "All"}
          </button>
        ))}
        <div className="flex items-center gap-3 ml-auto">
          {selected.size > 0 && (
            <button onClick={handleBulkDelete}
              className="px-3 py-1.5 text-xs font-medium border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors">
              Delete {selected.size} job{selected.size !== 1 ? "s" : ""}
            </button>
          )}
          {jobs.length > 0 && (
            <button onClick={toggleAll} className="text-xs text-indigo-400 hover:text-indigo-300 font-medium">
              {selected.size === jobs.length ? "Deselect" : "Select All"}
            </button>
          )}
          <span className="text-sm text-[var(--muted)]">{total} total</span>
        </div>
      </div>

      {loading ? (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center text-[var(--muted)]">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center text-[var(--muted)]">No jobs yet</div>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <div key={job.id} className={`bg-[var(--card)] border rounded-xl p-4 transition-colors hover:border-[var(--muted)] ${selected.has(job.id) ? "border-indigo-500/40 bg-indigo-500/5" : "border-[var(--card-border)]"}`}>
              <div className="flex items-center gap-4">
                <input type="checkbox" checked={selected.has(job.id)} onChange={() => toggleJob(job.id)}
                  className="w-4 h-4 rounded border-[var(--card-border)] text-indigo-600 focus:ring-indigo-500 flex-shrink-0" />
                {job.entry_thumbnail && (
                  <img src={job.entry_thumbnail} alt="" className="w-20 h-12 rounded-lg object-cover flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{job.entry_title || job.id}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`px-2 py-0.5 text-xs rounded-md font-medium ${STATUS_STYLES[job.status] || ""}`}>
                      {job.status}
                    </span>
                    {job.status === "running" && job.current_stage && (
                      <span className="text-xs text-indigo-400 font-medium capitalize">{job.current_stage}</span>
                    )}
                    {job.status === "running" && job.progress_pct > 0 && (
                      <span className="text-xs text-[var(--muted)]">
                        {job.progress_pct.toFixed(0)}%
                        {job.speed_bps ? ` \u00b7 ${formatBytes(job.speed_bps)}/s` : ""}
                      </span>
                    )}
                    {job.status === "running" && job.total_stages > 0 && (
                      <span className="text-xs text-[var(--muted)]">
                        Stage {job.completed_stages + 1}/{job.total_stages}
                      </span>
                    )}
                    {job.error_message && (
                      <span className="text-xs text-red-400 truncate max-w-xs">{job.error_message}</span>
                    )}
                  </div>
                  {job.status === "running" && (
                    <div className="mt-2 h-1.5 bg-[var(--background)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-indigo-500 to-blue-500 rounded-full transition-all duration-500"
                        style={{ width: `${job.total_stages > 0 ? Math.max(job.progress_pct, (job.completed_stages / job.total_stages) * 100) : job.progress_pct}%` }}
                      />
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => showDetail(job.id)} className="px-3 py-1.5 text-xs font-medium bg-[var(--background)] border border-[var(--card-border)] rounded-lg hover:border-[var(--muted)] transition-colors">Details</button>
                  {["pending", "queued", "running"].includes(job.status) && (
                    <button onClick={() => handleCancel(job.id)} className="px-3 py-1.5 text-xs font-medium border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors">Cancel</button>
                  )}
                  {job.status === "failed" && (
                    <button onClick={() => handleRetry(job.id)} className="px-3 py-1.5 text-xs font-medium border border-indigo-500/30 text-indigo-400 rounded-lg hover:bg-indigo-500/10 transition-colors">Retry</button>
                  )}
                  {job.status !== "running" && (
                    <button onClick={() => handleDeleteOne(job.id)} className="px-3 py-1.5 text-xs font-medium border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors">Delete</button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail modal */}
      {detail && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setDetail(null)}>
          <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-2xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-5">
              <h2 className="text-lg font-semibold truncate pr-4">{detail.entry_title || "Job Detail"}</h2>
              <button onClick={() => setDetail(null)} className="w-8 h-8 rounded-lg bg-[var(--background)] flex items-center justify-center text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">&times;</button>
            </div>

            {detail.request && (
              <div className="mb-5 p-4 bg-[var(--background)] rounded-xl text-sm space-y-1">
                <p><span className="text-[var(--muted)]">Format:</span> {detail.request.format_mode}</p>
                <p><span className="text-[var(--muted)]">Container:</span> {detail.request.container}</p>
                <p><span className="text-[var(--muted)]">SponsorBlock:</span> {detail.request.sponsorblock_action}</p>
                {detail.request.max_height && <p><span className="text-[var(--muted)]">Max height:</span> {detail.request.max_height}p</p>}
              </div>
            )}

            <h3 className="text-xs font-medium text-[var(--muted)] mb-3 uppercase tracking-wider">Stages</h3>
            <div className="space-y-2 mb-5">
              {detail.stages.map((stage) => (
                <div key={stage.id} className="flex items-center gap-3 text-sm">
                  <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                    stage.status === "completed" ? "bg-emerald-400" :
                    stage.status === "running" ? "bg-blue-400 animate-pulse" :
                    stage.status === "failed" ? "bg-red-400" : "bg-slate-500"
                  }`} />
                  <span className="flex-1">{stage.type.replace(/_/g, " ")}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-md ${STATUS_STYLES[stage.status] || ""}`}>{stage.status}</span>
                </div>
              ))}
            </div>

            {detail.artifacts.length > 0 && (
              <>
                <h3 className="text-xs font-medium text-[var(--muted)] mb-3 uppercase tracking-wider">Files</h3>
                <div className="space-y-2">
                  {detail.artifacts.map((a) => (
                    <div key={a.id} className={`p-3 rounded-xl ${a.file_exists ? "bg-[var(--background)]" : "bg-red-500/5 border border-red-500/20"}`}>
                      <div className="flex items-center justify-between">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium truncate">{a.filename}</p>
                          <p className="text-xs text-[var(--muted)] mt-0.5">
                            {a.kind} &middot; {formatBytes(a.size_bytes)}
                            {!a.file_exists && <span className="text-red-400 ml-2">Source file deleted or moved</span>}
                          </p>
                        </div>
                        {a.file_exists && a.download_url && (
                          <a href={a.download_url} download className="px-3 py-1.5 text-xs font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors flex-shrink-0 ml-3">Download</a>
                        )}
                      </div>
                      {!a.file_exists && !a.download_url && (
                        <p className="text-xs text-red-400/70 mt-1">File no longer available on server</p>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}

            {detail.error_message && (
              <div className="mt-5 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400">{detail.error_message}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
