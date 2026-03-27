"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";

interface ArchiveRecord {
  id: string;
  external_video_id: string;
  canonical_url: string;
  output_signature_hash: string;
  artifact_id: string | null;
  first_downloaded_at: string;
  title: string | null;
  thumbnail_url: string | null;
  uploader: string | null;
}

export default function ArchivePage() {
  const [records, setRecords] = useState<ArchiveRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const fetchRecords = useCallback(async (q?: string) => {
    try {
      const params = new URLSearchParams();
      params.set("per_page", "100");
      if (q) params.set("search", q);
      const res = await apiFetch<{ records: ArchiveRecord[]; total: number }>(
        `/api/archive?${params}`
      );
      setRecords(res.records);
      setTotal(res.total);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchRecords(); }, [fetchRecords]);

  const handleSearch = (val: string) => {
    setSearch(val);
    const t = setTimeout(() => fetchRecords(val), 300);
    return () => clearTimeout(t);
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === records.length) setSelected(new Set());
    else setSelected(new Set(records.map((r) => r.id)));
  };

  const handleDelete = async (ids: string[]) => {
    if (!confirm(`Remove ${ids.length} archive record${ids.length !== 1 ? "s" : ""}? This allows those videos to be downloaded again.`)) return;
    try {
      await apiFetch("/api/archive/bulk-delete", {
        method: "POST",
        body: JSON.stringify({ record_ids: ids }),
      });
      setSelected(new Set());
      fetchRecords(search);
    } catch { /* ignore */ }
  };

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto w-full">
      <h1 className="text-2xl font-bold mb-1">Archive</h1>
      <p className="text-sm text-[var(--muted)] mb-6">
        Download history used to prevent duplicate downloads. <strong>No files are stored here</strong> — only metadata references.
        Remove a record to allow re-downloading that video.
      </p>

      {/* Search + actions bar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="Search by title or video ID..."
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="flex-1 min-w-[200px] px-4 py-2 bg-[var(--card)] border border-[var(--card-border)] rounded-lg text-sm"
        />
        <span className="text-sm text-[var(--muted)]">{total} record{total !== 1 ? "s" : ""}</span>
      </div>

      {/* Bulk actions */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={toggleAll} className="text-sm text-indigo-400 hover:text-indigo-300">
          {selected.size === records.length && records.length > 0 ? "Deselect All" : "Select All"}
        </button>
        {selected.size > 0 && (
          <>
            <span className="text-sm text-[var(--muted)]">{selected.size} selected</span>
            <button
              onClick={() => handleDelete(Array.from(selected))}
              className="px-3 py-1.5 text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500/20"
            >
              Remove {selected.size} from Archive
            </button>
          </>
        )}
      </div>

      {/* Records list */}
      <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl overflow-hidden">
        {records.length === 0 ? (
          <div className="p-12 text-center text-[var(--muted)]">
            {search ? "No matching records" : "Archive is empty — no downloads recorded yet"}
          </div>
        ) : (
          <div className="divide-y divide-[var(--card-border)]">
            {records.map((rec) => (
              <div key={rec.id} className="flex items-center gap-4 px-4 py-3 hover:bg-white/5 transition-colors">
                <input
                  type="checkbox"
                  checked={selected.has(rec.id)}
                  onChange={() => toggleSelect(rec.id)}
                  className="w-4 h-4 rounded"
                  aria-label={`Select ${rec.title || rec.external_video_id}`}
                />
                {rec.thumbnail_url ? (
                  <img src={rec.thumbnail_url} alt="" className="w-16 h-10 rounded object-cover flex-shrink-0" />
                ) : (
                  <div className="w-16 h-10 rounded bg-[var(--card-border)] flex items-center justify-center flex-shrink-0">
                    <svg className="w-5 h-5 text-[var(--muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {rec.title || rec.external_video_id}
                  </p>
                  <p className="text-xs text-[var(--muted)]">
                    {rec.uploader && <>{rec.uploader} &middot; </>}
                    Downloaded {new Date(rec.first_downloaded_at).toLocaleDateString()}
                    {" "}&middot; ID: {rec.external_video_id}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete([rec.id])}
                  className="px-3 py-1.5 text-xs font-medium text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500/10 flex-shrink-0"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
