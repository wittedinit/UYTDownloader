"use client";

import { useState, useEffect, useCallback } from "react";
import { listJobs, cancelJob, retryJob, getJob, type Job, type JobDetail } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  queued: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-200 text-gray-600",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");
  const [detail, setDetail] = useState<JobDetail | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await listJobs({ status: filter || undefined });
      setJobs(res.jobs);
      setTotal(res.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const handleCancel = async (jobId: string) => {
    try {
      await cancelJob(jobId);
      fetchJobs();
    } catch {
      // ignore
    }
  };

  const handleRetry = async (jobId: string) => {
    try {
      await retryJob(jobId);
      fetchJobs();
    } catch {
      // ignore
    }
  };

  const showDetail = async (jobId: string) => {
    try {
      const d = await getJob(jobId);
      setDetail(d);
    } catch {
      // ignore
    }
  };

  const formatBytes = (bytes: number | null) => {
    if (!bytes) return "-";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  return (
    <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Jobs</h1>
        <a href="/" className="text-sm text-blue-600 hover:underline">
          New Download
        </a>
      </div>

      {/* Filter */}
      <div className="flex gap-2 mb-4">
        {["", "queued", "running", "completed", "failed"].map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 text-sm rounded-full border ${
              filter === s
                ? "bg-blue-600 text-white border-blue-600"
                : "border-gray-300 hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-800"
            }`}
          >
            {s || "All"}
          </button>
        ))}
        <span className="text-sm text-gray-500 self-center ml-auto">{total} total</span>
      </div>

      {loading ? (
        <p className="text-center py-8 text-gray-500">Loading...</p>
      ) : jobs.length === 0 ? (
        <p className="text-center py-8 text-gray-500">No jobs yet</p>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="p-3 border rounded-md hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800"
            >
              <div className="flex items-center gap-3">
                {job.entry_thumbnail && (
                  <img src={job.entry_thumbnail} alt="" className="w-16 h-10 rounded object-cover flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{job.entry_title || job.id}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span
                      className={`px-2 py-0.5 text-xs rounded-full font-medium ${STATUS_COLORS[job.status] || ""}`}
                    >
                      {job.status}
                    </span>
                    {job.status === "running" && (
                      <span className="text-xs text-gray-500">
                        {job.progress_pct.toFixed(0)}%
                        {job.speed_bps ? ` \u00b7 ${formatBytes(job.speed_bps)}/s` : ""}
                      </span>
                    )}
                    {job.error_message && (
                      <span className="text-xs text-red-500 truncate max-w-xs">{job.error_message}</span>
                    )}
                  </div>
                  {/* Progress bar */}
                  {job.status === "running" && (
                    <div className="mt-1 h-1 bg-gray-200 rounded-full overflow-hidden dark:bg-gray-700">
                      <div
                        className="h-full bg-blue-500 transition-all"
                        style={{ width: `${job.progress_pct}%` }}
                      />
                    </div>
                  )}
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => showDetail(job.id)}
                    className="px-2 py-1 text-xs border rounded hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-700"
                  >
                    Details
                  </button>
                  {(job.status === "pending" || job.status === "queued" || job.status === "running") && (
                    <button
                      onClick={() => handleCancel(job.id)}
                      className="px-2 py-1 text-xs border border-red-300 text-red-600 rounded hover:bg-red-50"
                    >
                      Cancel
                    </button>
                  )}
                  {job.status === "failed" && (
                    <button
                      onClick={() => handleRetry(job.id)}
                      className="px-2 py-1 text-xs border border-blue-300 text-blue-600 rounded hover:bg-blue-50"
                    >
                      Retry
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Detail modal */}
      {detail && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-lg w-full max-h-[80vh] overflow-y-auto p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">{detail.entry_title || "Job Detail"}</h2>
              <button onClick={() => setDetail(null)} className="text-gray-400 hover:text-gray-600 text-xl">
                &times;
              </button>
            </div>

            {/* Request info */}
            {detail.request && (
              <div className="mb-4 p-3 bg-gray-50 rounded text-sm dark:bg-gray-800">
                <p>Format: {detail.request.format_mode}</p>
                <p>Container: {detail.request.container}</p>
                <p>SponsorBlock: {detail.request.sponsorblock_action}</p>
                {detail.request.max_height && <p>Max height: {detail.request.max_height}p</p>}
              </div>
            )}

            {/* Stages */}
            <h3 className="text-sm font-semibold mb-2">Stages</h3>
            <div className="space-y-1 mb-4">
              {detail.stages.map((stage) => (
                <div key={stage.id} className="flex items-center gap-2 text-sm">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    stage.status === "completed" ? "bg-green-500" :
                    stage.status === "running" ? "bg-blue-500 animate-pulse" :
                    stage.status === "failed" ? "bg-red-500" : "bg-gray-300"
                  }`} />
                  <span className="flex-1">{stage.type.replace(/_/g, " ")}</span>
                  <span className={`text-xs ${STATUS_COLORS[stage.status] || ""} px-1.5 py-0.5 rounded`}>
                    {stage.status}
                  </span>
                </div>
              ))}
            </div>

            {/* Artifacts */}
            {detail.artifacts.length > 0 && (
              <>
                <h3 className="text-sm font-semibold mb-2">Artifacts</h3>
                <div className="space-y-1">
                  {detail.artifacts.map((a) => (
                    <div key={a.id} className="text-sm p-2 bg-gray-50 rounded dark:bg-gray-800">
                      <p className="font-medium truncate">{a.filename}</p>
                      <p className="text-xs text-gray-500">
                        {a.kind} &middot; {formatBytes(a.size_bytes)}
                      </p>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* Error */}
            {detail.error_message && (
              <div className="mt-4 p-3 bg-red-50 rounded text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
                {detail.error_message}
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
