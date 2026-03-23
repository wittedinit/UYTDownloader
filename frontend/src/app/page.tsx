"use client";

import { useState, useCallback } from "react";
import { submitProbe, pollProbe, createJobs, type Entry, type Source } from "@/lib/api";

type Phase = "input" | "probing" | "select" | "queued" | "error";

export default function Home() {
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("input");
  const [error, setError] = useState("");
  const [source, setSource] = useState<Source | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Download options
  const [formatMode, setFormatMode] = useState("video_audio");
  const [quality, setQuality] = useState("best");
  const [sponsorblock, setSponsorblock] = useState("keep");
  const [embedSubs, setEmbedSubs] = useState(false);
  const [normalizeAudio, setNormalizeAudio] = useState(false);

  const handleProbe = useCallback(async () => {
    if (!url.trim()) return;
    setPhase("probing");
    setError("");
    try {
      const { probe_id } = await submitProbe(url.trim());
      let attempts = 0;
      while (attempts < 60) {
        await new Promise((r) => setTimeout(r, 2000));
        const result = await pollProbe(probe_id);
        if (result.status === "completed" && result.source) {
          setSource(result.source);
          const allEntries = result.source.entries || [];
          setEntries(allEntries);
          setSelected(new Set(allEntries.map((e) => e.id)));
          setPhase("select");
          return;
        }
        if (result.status === "failed") {
          setError(result.error || "Probe failed");
          setPhase("error");
          return;
        }
        attempts++;
      }
      setError("Probe timed out");
      setPhase("error");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setPhase("error");
    }
  }, [url]);

  const handleDownload = useCallback(async () => {
    if (selected.size === 0) return;
    try {
      await createJobs({
        entry_ids: Array.from(selected),
        format_mode: formatMode,
        quality,
        sponsorblock_action: sponsorblock,
        embed_subtitles: embedSubs,
        normalize_audio: normalizeAudio,
      });
      setPhase("queued");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create jobs");
      setPhase("error");
    }
  }, [selected, formatMode, quality, sponsorblock, embedSubs, normalizeAudio]);

  const toggleEntry = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === entries.length) setSelected(new Set());
    else setSelected(new Set(entries.map((e) => e.id)));
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "--:--";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${m}:${String(s).padStart(2, "0")}`;
  };

  return (
    <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">UYTDownloader</h1>
        <a href="/jobs" className="text-sm text-blue-600 hover:underline">
          View Jobs
        </a>
      </div>

      {/* URL Input */}
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleProbe()}
          placeholder="Paste YouTube URL (video, playlist, or channel)"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-600 dark:text-white"
          disabled={phase === "probing"}
        />
        <button
          onClick={handleProbe}
          disabled={phase === "probing" || !url.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {phase === "probing" ? "Probing..." : "Probe"}
        </button>
      </div>

      {/* Error */}
      {phase === "error" && (
        <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-800 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300">
          {error}
          <button onClick={() => setPhase("input")} className="ml-2 underline">
            Try again
          </button>
        </div>
      )}

      {/* Probing spinner */}
      {phase === "probing" && (
        <div className="text-center py-12 text-gray-500">
          <div className="inline-block w-8 h-8 border-4 border-blue-300 border-t-blue-600 rounded-full animate-spin mb-4" />
          <p>Extracting metadata...</p>
        </div>
      )}

      {/* Selection phase */}
      {phase === "select" && source && (
        <div>
          {/* Source info */}
          <div className="mb-4 p-4 bg-gray-50 rounded-md dark:bg-gray-800">
            <div className="flex items-center gap-3">
              {source.thumbnail_url && (
                <img src={source.thumbnail_url} alt="" className="w-16 h-16 rounded object-cover" />
              )}
              <div>
                <h2 className="font-semibold">{source.title || "Unknown"}</h2>
                <p className="text-sm text-gray-500">
                  {source.type} &middot; {source.uploader || "Unknown"} &middot; {entries.length} items
                </p>
              </div>
            </div>
          </div>

          {/* Download options */}
          <div className="mb-4 grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Output</label>
              <select
                value={formatMode}
                onChange={(e) => setFormatMode(e.target.value)}
                className="w-full px-2 py-1.5 border rounded text-sm dark:bg-gray-800 dark:border-gray-600"
              >
                <option value="video_audio">Video + Audio</option>
                <option value="audio_only">Audio Only</option>
                <option value="video_only">Video Only</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Quality</label>
              <select
                value={quality}
                onChange={(e) => setQuality(e.target.value)}
                className="w-full px-2 py-1.5 border rounded text-sm dark:bg-gray-800 dark:border-gray-600"
              >
                <option value="best">Best Available</option>
                <option value="1080p">1080p</option>
                <option value="720p">720p</option>
                <option value="480p">480p</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">SponsorBlock</label>
              <select
                value={sponsorblock}
                onChange={(e) => setSponsorblock(e.target.value)}
                className="w-full px-2 py-1.5 border rounded text-sm dark:bg-gray-800 dark:border-gray-600"
              >
                <option value="keep">Keep All</option>
                <option value="mark_chapters">Mark as Chapters</option>
                <option value="remove">Remove Sponsors</option>
              </select>
            </div>
          </div>

          {/* Post-processing options */}
          <div className="mb-4 flex gap-6">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={embedSubs}
                onChange={(e) => setEmbedSubs(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              Embed subtitles
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={normalizeAudio}
                onChange={(e) => setNormalizeAudio(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              Normalize audio
            </label>
          </div>

          {/* Entry list */}
          <div className="mb-4 flex items-center justify-between">
            <button onClick={toggleAll} className="text-sm text-blue-600 hover:underline">
              {selected.size === entries.length ? "Deselect All" : "Select All"}
            </button>
            <span className="text-sm text-gray-500">{selected.size} selected</span>
          </div>

          <div className="space-y-1 max-h-96 overflow-y-auto mb-6">
            {entries.map((entry) => (
              <label
                key={entry.id}
                className="flex items-center gap-3 p-2 rounded hover:bg-gray-50 cursor-pointer dark:hover:bg-gray-800"
              >
                <input
                  type="checkbox"
                  checked={selected.has(entry.id)}
                  onChange={() => toggleEntry(entry.id)}
                  className="w-4 h-4 rounded"
                />
                {entry.thumbnail_url && (
                  <img src={entry.thumbnail_url} alt="" className="w-20 h-12 rounded object-cover flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{entry.title}</p>
                  <p className="text-xs text-gray-500">
                    {formatDuration(entry.duration)}
                    {entry.upload_date && ` \u00b7 ${entry.upload_date}`}
                  </p>
                </div>
              </label>
            ))}
          </div>

          {/* Download button */}
          <button
            onClick={handleDownload}
            disabled={selected.size === 0}
            className="w-full py-3 bg-green-600 text-white rounded-md font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Download {selected.size} item{selected.size !== 1 ? "s" : ""}
          </button>
        </div>
      )}

      {/* Queued confirmation */}
      {phase === "queued" && (
        <div className="text-center py-12">
          <p className="text-lg font-medium text-green-600 mb-2">Jobs queued!</p>
          <p className="text-sm text-gray-500 mb-4">
            {selected.size} download{selected.size !== 1 ? "s" : ""} added to the queue.
          </p>
          <div className="flex gap-3 justify-center">
            <a
              href="/jobs"
              className="px-4 py-2 bg-gray-100 rounded-md text-sm hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700"
            >
              View Jobs
            </a>
            <button
              onClick={() => {
                setPhase("input");
                setUrl("");
                setSource(null);
                setEntries([]);
                setSelected(new Set());
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
            >
              Download More
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
