"use client";

import { useState, useEffect, useCallback } from "react";
import { listLibraryFiles, deleteLibraryFile, mergeLibraryFiles, type LibraryFile } from "@/lib/api";

function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    if (window.location.hostname.endsWith(".orb.local")) return "http://uyt-backend-1.orb.local:8000";
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

export default function LibraryPage() {
  const [files, setFiles] = useState<LibraryFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [merging, setMerging] = useState(false);
  const apiBase = resolveApiBase();

  const fetchFiles = useCallback(async () => {
    try { const res = await listLibraryFiles(); setFiles(res.files); }
    catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  const toggleFile = (f: string) => setSelected((prev) => { const n = new Set(prev); if (n.has(f)) n.delete(f); else n.add(f); return n; });
  const toggleAll = () => { if (selected.size === files.length) setSelected(new Set()); else setSelected(new Set(files.map((f) => f.filename))); };

  const handleDownloadSelected = () => {
    for (const filename of selected) {
      const link = document.createElement("a");
      link.href = `${apiBase}/api/library/download/${encodeURIComponent(filename)}`;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`Delete "${filename}"?`)) return;
    try { await deleteLibraryFile(filename); setSelected((p) => { const n = new Set(p); n.delete(filename); return n; }); fetchFiles(); }
    catch { alert("Failed to delete"); }
  };

  const formatBytes = (b: number) => {
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
    if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`;
    return `${(b / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const formatDate = (ts: number) => new Date(ts * 1000).toLocaleString();

  const iconForExt = (ext: string) => {
    if ([".mp4", ".mkv", ".webm", ".avi"].includes(ext)) return "video";
    if ([".mp3", ".m4a", ".opus", ".ogg", ".webm"].includes(ext)) return "audio";
    return "file";
  };

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Library</h1>
        <p className="text-sm text-[var(--muted)]">Browse and download completed files</p>
      </div>

      {loading ? (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center text-[var(--muted)]">Loading...</div>
      ) : files.length === 0 ? (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center text-[var(--muted)]">No downloads yet</div>
      ) : (
        <>
          {/* Stats bar */}
          <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-4 mb-6 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button onClick={toggleAll} className="text-sm text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
                {selected.size === files.length ? "Deselect All" : "Select All"}
              </button>
              <span className="text-sm text-[var(--muted)]">{selected.size} selected</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-[var(--muted)]">{files.length} files &middot; {formatBytes(files.reduce((s, f) => s + f.size_bytes, 0))}</span>
              {selected.size > 0 && (
                <div className="flex gap-2">
                  <button onClick={handleDownloadSelected}
                    className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-green-600 text-white rounded-lg text-sm font-medium hover:from-emerald-700 hover:to-green-700 transition-all">
                    Download {selected.size}
                  </button>
                  {selected.size >= 2 && (
                    <button
                      disabled={merging}
                      onClick={async () => {
                        const title = prompt("Merged file name:", "Merged Compilation") || "Merged Compilation";
                        const hasVideo = Array.from(selected).some((f) => f.endsWith(".mp4") || f.endsWith(".mkv") || f.endsWith(".webm"));
                        setMerging(true);
                        try {
                          await mergeLibraryFiles({
                            filenames: Array.from(selected),
                            title,
                            mode: hasVideo ? "video_chapters" : "audio_chapters",
                          });
                          setSelected(new Set());
                          fetchFiles();
                          alert("Merge complete!");
                        } catch (e) {
                          alert(e instanceof Error ? e.message : "Merge failed");
                        } finally { setMerging(false); }
                      }}
                      className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg text-sm font-medium hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 transition-all">
                      {merging ? "Merging..." : `Merge ${selected.size}`}
                    </button>
                  )}
                  <button onClick={async () => {
                    if (!confirm(`Delete ${selected.size} file${selected.size !== 1 ? "s" : ""}?`)) return;
                    for (const f of selected) { try { await deleteLibraryFile(f); } catch {} }
                    setSelected(new Set());
                    fetchFiles();
                  }}
                    className="px-4 py-2 border border-red-500/30 text-red-400 rounded-lg text-sm font-medium hover:bg-red-500/10 transition-colors">
                    Delete {selected.size} file{selected.size !== 1 ? "s" : ""}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* File list */}
          <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl overflow-hidden">
            <div className="divide-y divide-[var(--card-border)]">
              {files.map((file) => (
                <label key={file.filename}
                  className={`flex items-center gap-4 px-5 py-4 cursor-pointer transition-colors ${selected.has(file.filename) ? "bg-indigo-500/5" : "hover:bg-[var(--background)]"}`}>
                  <input type="checkbox" checked={selected.has(file.filename)} onChange={() => toggleFile(file.filename)}
                    className="w-4 h-4 rounded border-[var(--card-border)] text-indigo-600 focus:ring-indigo-500" />
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    iconForExt(file.extension) === "video" ? "bg-blue-500/10" : iconForExt(file.extension) === "audio" ? "bg-purple-500/10" : "bg-slate-500/10"
                  }`}>
                    <svg className={`w-5 h-5 ${iconForExt(file.extension) === "video" ? "text-blue-400" : iconForExt(file.extension) === "audio" ? "text-purple-400" : "text-slate-400"}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      {iconForExt(file.extension) === "video" ? (
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9.75a2.25 2.25 0 002.25-2.25V7.5a2.25 2.25 0 00-2.25-2.25H4.5A2.25 2.25 0 002.25 7.5v9A2.25 2.25 0 004.5 18.75z" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V4.5A2.25 2.25 0 0117.25 2.25H21" />
                      )}
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{file.filename}</p>
                    <p className="text-xs text-[var(--muted)] mt-0.5">{formatBytes(file.size_bytes)} &middot; {formatDate(file.modified_at)}</p>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <a href={`${apiBase}/api/library/download/${encodeURIComponent(file.filename)}`} download={file.filename}
                      onClick={(e) => e.stopPropagation()}
                      className="px-3 py-1.5 text-xs font-medium bg-[var(--background)] border border-[var(--card-border)] rounded-lg hover:border-[var(--muted)] transition-colors">
                      Download
                    </a>
                    <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleDelete(file.filename); }}
                      className="px-3 py-1.5 text-xs font-medium border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors">
                      Delete
                    </button>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
