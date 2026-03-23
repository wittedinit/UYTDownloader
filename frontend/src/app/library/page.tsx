"use client";

import { useState, useEffect, useCallback } from "react";
import { listLibraryFiles, deleteLibraryFile, type LibraryFile } from "@/lib/api";

const API_BASE = typeof window !== "undefined"
  ? window.location.hostname.endsWith(".orb.local")
    ? "http://uyt-backend-1.orb.local:8000"
    : `${window.location.protocol}//${window.location.hostname}:8000`
  : "http://localhost:8000";

export default function LibraryPage() {
  const [files, setFiles] = useState<LibraryFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const fetchFiles = useCallback(async () => {
    try {
      const res = await listLibraryFiles();
      setFiles(res.files);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const toggleFile = (filename: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === files.length) setSelected(new Set());
    else setSelected(new Set(files.map((f) => f.filename)));
  };

  const handleDownloadSelected = () => {
    // Download each selected file by opening download URLs
    for (const filename of selected) {
      const file = files.find((f) => f.filename === filename);
      if (file) {
        const link = document.createElement("a");
        link.href = `${API_BASE}/api/library/download/${encodeURIComponent(file.filename)}`;
        link.download = file.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    }
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`Delete "${filename}"?`)) return;
    try {
      await deleteLibraryFile(filename);
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(filename);
        return next;
      });
      fetchFiles();
    } catch {
      alert("Failed to delete file");
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const formatDate = (ts: number) => new Date(ts * 1000).toLocaleString();

  const iconForExt = (ext: string) => {
    if ([".mp4", ".mkv", ".webm", ".avi"].includes(ext)) return "🎬";
    if ([".mp3", ".m4a", ".opus", ".ogg", ".webm"].includes(ext)) return "🎵";
    return "📄";
  };

  return (
    <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Library</h1>
        <div className="flex gap-3">
          <a href="/subscriptions" className="text-sm text-blue-600 hover:underline">Subscriptions</a>
          <a href="/jobs" className="text-sm text-blue-600 hover:underline">Jobs</a>
          <a href="/" className="text-sm text-blue-600 hover:underline">New Download</a>
        </div>
      </div>

      {loading ? (
        <p className="text-center py-8 text-gray-500">Loading...</p>
      ) : files.length === 0 ? (
        <p className="text-center py-8 text-gray-500">No downloads yet</p>
      ) : (
        <>
          {/* Actions bar */}
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button onClick={toggleAll} className="text-sm text-blue-600 hover:underline">
                {selected.size === files.length ? "Deselect All" : "Select All"}
              </button>
              <span className="text-sm text-gray-500">{selected.size} selected</span>
            </div>
            {selected.size > 0 && (
              <button
                onClick={handleDownloadSelected}
                className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700"
              >
                Download {selected.size} file{selected.size !== 1 ? "s" : ""}
              </button>
            )}
          </div>

          {/* File list */}
          <div className="space-y-1">
            {files.map((file) => (
              <label
                key={file.filename}
                className="flex items-center gap-3 p-3 rounded-md hover:bg-gray-50 cursor-pointer dark:hover:bg-gray-800"
              >
                <input
                  type="checkbox"
                  checked={selected.has(file.filename)}
                  onChange={() => toggleFile(file.filename)}
                  className="w-4 h-4 rounded"
                />
                <span className="text-lg flex-shrink-0">{iconForExt(file.extension)}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{file.filename}</p>
                  <p className="text-xs text-gray-500">
                    {formatBytes(file.size_bytes)} &middot; {formatDate(file.modified_at)}
                  </p>
                </div>
                <div className="flex gap-1 flex-shrink-0">
                  <a
                    href={`${API_BASE}/api/library/download/${encodeURIComponent(file.filename)}`}
                    download={file.filename}
                    className="px-2 py-1 text-xs border rounded hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-700"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Download
                  </a>
                  <button
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleDelete(file.filename); }}
                    className="px-2 py-1 text-xs border border-red-300 text-red-600 rounded hover:bg-red-50"
                  >
                    Delete
                  </button>
                </div>
              </label>
            ))}
          </div>

          {/* Total size */}
          <div className="mt-4 text-sm text-gray-500 text-right">
            {files.length} files &middot; {formatBytes(files.reduce((sum, f) => sum + f.size_bytes, 0))} total
          </div>
        </>
      )}
    </main>
  );
}
