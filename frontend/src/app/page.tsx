"use client";

import { useState, useCallback, useEffect } from "react";
import { submitProbe, pollProbe, createJobs, createSubscription, createCompilation, type Entry, type Source } from "@/lib/api";

type Phase = "input" | "probing" | "select" | "queued" | "error";

// Session storage helpers
function saveSession(data: Record<string, unknown>) {
  try { sessionStorage.setItem("uyt_probe", JSON.stringify(data)); } catch {}
}
function loadSession(): Record<string, unknown> | null {
  try {
    const raw = sessionStorage.getItem("uyt_probe");
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export default function Home() {
  const saved = typeof window !== "undefined" ? loadSession() : null;

  const [url, setUrl] = useState((saved?.url as string) || "");
  const [phase, setPhase] = useState<Phase>((saved?.phase as Phase) || "input");
  const [error, setError] = useState((saved?.error as string) || "");
  const [source, setSource] = useState<Source | null>((saved?.source as Source) || null);
  const [entries, setEntries] = useState<Entry[]>((saved?.entries as Entry[]) || []);
  const [selected, setSelected] = useState<Set<string>>(new Set((saved?.selected as string[]) || []));

  const [formatMode, setFormatMode] = useState((saved?.formatMode as string) || "video_audio");
  const [quality, setQuality] = useState((saved?.quality as string) || "best");
  const [sponsorblock, setSponsorblock] = useState((saved?.sponsorblock as string) || "keep");
  const [embedSubs, setEmbedSubs] = useState((saved?.embedSubs as boolean) || false);
  const [normalizeAudio, setNormalizeAudio] = useState((saved?.normalizeAudio as boolean) || false);
  const [outputFormat, setOutputFormat] = useState((saved?.outputFormat as string) || "original");
  const [videoBitrate, setVideoBitrate] = useState((saved?.videoBitrate as string) || "auto");

  // Persist state to sessionStorage on changes
  useEffect(() => {
    if (phase === "probing") return; // Don't save mid-probe
    saveSession({
      url, phase, error, source, entries,
      selected: Array.from(selected),
      formatMode, quality, sponsorblock, embedSubs, normalizeAudio,
      outputFormat, videoBitrate,
    });
  }, [url, phase, error, source, entries, selected, formatMode, quality, sponsorblock, embedSubs, normalizeAudio, outputFormat, videoBitrate]);

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
          const allEntries = result.entries || [];
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
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Download</h1>
        <p className="text-sm text-[var(--muted)]">Paste a YouTube URL to probe and download videos</p>
      </div>

      {/* URL Input Card */}
      <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-6 mb-6">
        <label className="block text-xs font-medium text-[var(--muted)] mb-2 uppercase tracking-wider">YouTube URL</label>
        <div className="flex gap-3">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleProbe()}
            placeholder="https://youtube.com/watch?v=... or playlist or channel URL"
            className="flex-1 px-4 py-3 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent placeholder:text-[var(--muted)]"
            disabled={phase === "probing"}
          />
          <button
            onClick={handleProbe}
            disabled={phase === "probing" || !url.trim()}
            className="px-6 py-3 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {phase === "probing" ? (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                Probing
              </span>
            ) : "Probe"}
          </button>
        </div>
      </div>

      {/* Error */}
      {phase === "error" && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setPhase("input")} className="text-red-300 hover:text-white text-xs font-medium px-3 py-1 rounded-md bg-red-500/20 hover:bg-red-500/30 transition-colors">
            Try again
          </button>
        </div>
      )}

      {/* Probing state */}
      {phase === "probing" && (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center">
          <div className="inline-block w-10 h-10 border-3 border-indigo-400/30 border-t-indigo-500 rounded-full animate-spin mb-4" />
          <p className="text-[var(--muted)]">Extracting metadata...</p>
        </div>
      )}

      {/* Selection phase */}
      {phase === "select" && source && (
        <>
          {/* Source card */}
          <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-5 mb-6">
            <div className="flex items-center gap-4">
              {source.thumbnail_url && (
                <img src={source.thumbnail_url} alt="" className="w-20 h-14 rounded-lg object-cover" />
              )}
              <div className="flex-1 min-w-0">
                <h2 className="font-semibold text-lg truncate">{source.title || "Unknown"}</h2>
                <p className="text-sm text-[var(--muted)]">
                  <span className="inline-block px-2 py-0.5 bg-indigo-500/10 text-indigo-400 rounded text-xs font-medium mr-2">{source.type}</span>
                  {source.uploader || "Unknown"} &middot; {entries.length} item{entries.length !== 1 ? "s" : ""}
                </p>
              </div>
              {(source.type === "playlist" || source.type === "channel") && (
                <button
                  onClick={async () => {
                    try {
                      await createSubscription({
                        source_id: source.id,
                        format_mode: formatMode,
                        quality,
                        sponsorblock_action: sponsorblock,
                        filters: [{ filter_type: "ignore_shorts" }],
                      });
                      alert("Subscribed! New videos will be downloaded automatically.");
                    } catch (e) {
                      alert(e instanceof Error ? e.message : "Failed to subscribe");
                    }
                  }}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg text-xs font-medium hover:bg-purple-700 transition-colors flex-shrink-0"
                >
                  Subscribe
                </button>
              )}
            </div>
          </div>

          {/* Options card */}
          <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-5 mb-6">
            <h3 className="text-xs font-medium text-[var(--muted)] mb-4 uppercase tracking-wider">Download Options</h3>

            {/* Row 1: Stream type + Quality + SponsorBlock */}
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-xs text-[var(--muted)] mb-1.5">Stream</label>
                <select value={formatMode} onChange={(e) => { setFormatMode(e.target.value); setQuality("best"); setOutputFormat("original"); setVideoBitrate("auto"); }}
                  className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  <option value="video_audio">Video + Audio</option>
                  <option value="audio_only">Audio Only</option>
                  <option value="video_only">Video Only</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--muted)] mb-1.5">
                  {formatMode === "audio_only" ? "Audio Quality" : "Resolution"}
                </label>
                <select value={quality} onChange={(e) => setQuality(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  {formatMode === "audio_only" ? (
                    <>
                      <option value="best">Best Available</option>
                      <option value="audio_320k">320 kbps (Best Quality)</option>
                      <option value="audio_256k">256 kbps (High)</option>
                      <option value="audio_192k">192 kbps (Recommended)</option>
                      <option value="audio_128k">128 kbps (Good)</option>
                      <option value="audio_64k">64 kbps (Smallest Size)</option>
                    </>
                  ) : (
                    <>
                      <option value="best">Best Available</option>
                      <option value="2160p">2160p / 4K (Best Quality)</option>
                      <option value="1080p">1080p (Recommended)</option>
                      <option value="720p">720p (Balanced)</option>
                      <option value="480p">480p (Smallest Size)</option>
                    </>
                  )}
                </select>
              </div>
              <div>
                <label className="block text-xs text-[var(--muted)] mb-1.5">SponsorBlock</label>
                <select value={sponsorblock} onChange={(e) => setSponsorblock(e.target.value)}
                  className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  <option value="keep">Keep All</option>
                  <option value="mark_chapters">Mark as Chapters</option>
                  <option value="remove">Remove Sponsors</option>
                </select>
              </div>
            </div>

            {/* Row 2: Output format + Bitrate (video modes only) */}
            {formatMode !== "audio_only" && (
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-xs text-[var(--muted)] mb-1.5">Output Format</label>
                  <select value={outputFormat} onChange={(e) => setOutputFormat(e.target.value)}
                    className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    <option value="original">Original (No Re-encode)</option>
                    <option value="mp4_h264">MP4 / H.264 (Recommended)</option>
                    <option value="mp4_h265">MP4 / H.265 (Smaller Size)</option>
                    <option value="mkv_h264">MKV / H.264</option>
                    <option value="webm_vp9">WebM / VP9</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-[var(--muted)] mb-1.5">Video Bitrate</label>
                  <select value={videoBitrate} onChange={(e) => setVideoBitrate(e.target.value)}
                    className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    disabled={outputFormat === "original"}>
                    <option value="auto">Auto (Match Source)</option>
                    <option value="8000k">8,000 kbps (Best Quality)</option>
                    <option value="5000k">5,000 kbps (Recommended for 1080p)</option>
                    <option value="3000k">3,000 kbps (Good for 720p)</option>
                    <option value="1500k">1,500 kbps (Balanced)</option>
                    <option value="800k">800 kbps (Smallest Size)</option>
                  </select>
                </div>
              </div>
            )}

            {/* Audio output format (audio-only mode) */}
            {formatMode === "audio_only" && (
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-xs text-[var(--muted)] mb-1.5">Audio Format</label>
                  <select value={outputFormat} onChange={(e) => setOutputFormat(e.target.value)}
                    className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    <option value="original">Original (No Re-encode)</option>
                    <option value="mp3">MP3 (Most Compatible)</option>
                    <option value="m4a_aac">M4A / AAC (Recommended)</option>
                    <option value="opus">Opus (Best Quality/Size)</option>
                    <option value="flac">FLAC (Lossless)</option>
                  </select>
                </div>
                <div className="flex items-end">
                  {outputFormat !== "original" && outputFormat !== "flac" && (
                    <p className="text-xs text-[var(--muted)] pb-2">
                      Bitrate controlled by the Audio Quality setting above
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Info banner when re-encoding */}
            {outputFormat !== "original" && (
              <div className="mb-4 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-xs text-amber-400">
                Re-encoding will be applied after download. This uses {formatMode === "audio_only" ? "CPU" : "GPU if available, otherwise CPU"} and takes additional time.
              </div>
            )}

            {/* Row 3: Post-processing toggles */}
            <div className="flex gap-6">
              <label className="flex items-center gap-2 text-sm cursor-pointer text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">
                <input type="checkbox" checked={embedSubs} onChange={(e) => setEmbedSubs(e.target.checked)}
                  className="w-4 h-4 rounded border-[var(--card-border)] text-indigo-600 focus:ring-indigo-500" />
                Embed subtitles
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">
                <input type="checkbox" checked={normalizeAudio} onChange={(e) => setNormalizeAudio(e.target.checked)}
                  className="w-4 h-4 rounded border-[var(--card-border)] text-indigo-600 focus:ring-indigo-500" />
                Normalize audio
              </label>
            </div>
          </div>

          {/* Entries card */}
          <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl overflow-hidden mb-6">
            <div className="px-5 py-3 border-b border-[var(--card-border)] flex items-center justify-between">
              <button onClick={toggleAll} className="text-sm text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
                {selected.size === entries.length ? "Deselect All" : "Select All"}
              </button>
              <span className="text-sm text-[var(--muted)]">{selected.size} of {entries.length} selected</span>
            </div>
            <div className="max-h-[400px] overflow-y-auto divide-y divide-[var(--card-border)]">
              {entries.map((entry) => (
                <label
                  key={entry.id}
                  className={`flex items-center gap-4 px-5 py-3 cursor-pointer transition-colors ${
                    selected.has(entry.id) ? "bg-indigo-500/5" : "hover:bg-[var(--background)]"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(entry.id)}
                    onChange={() => toggleEntry(entry.id)}
                    className="w-4 h-4 rounded border-[var(--card-border)] text-indigo-600 focus:ring-indigo-500"
                  />
                  {entry.thumbnail_url && (
                    <img src={entry.thumbnail_url} alt="" className="w-24 h-14 rounded-md object-cover flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{entry.title}</p>
                    <p className="text-xs text-[var(--muted)] mt-0.5">
                      {formatDuration(entry.duration)}
                      {entry.upload_date && ` \u00b7 ${entry.upload_date}`}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Download buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleDownload}
              disabled={selected.size === 0}
              className="flex-1 py-4 bg-gradient-to-r from-emerald-600 to-green-600 text-white rounded-xl font-semibold text-base hover:from-emerald-700 hover:to-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-900/20"
            >
              Download {selected.size} item{selected.size !== 1 ? "s" : ""}
            </button>
            {selected.size >= 2 && (
              <button
                onClick={async () => {
                  const selectedEntries = entries.filter((e) => selected.has(e.id));
                  const title = source?.title
                    ? `${source.title} (Merged)`
                    : `Compilation ${new Date().toLocaleDateString()}`;
                  const isAudio = formatMode === "audio_only";
                  try {
                    await createCompilation({
                      items: selectedEntries.map((e, i) => ({ entry_id: e.id, position: i })),
                      mode: isAudio ? "audio_chapters" : "video_chapters",
                      title,
                      normalize_audio: normalizeAudio,
                    });
                    setPhase("queued");
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Merge failed — entries must be downloaded first");
                    setPhase("error");
                  }
                }}
                className="py-4 px-6 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl font-semibold text-base hover:from-purple-700 hover:to-indigo-700 transition-all shadow-lg shadow-purple-900/20"
              >
                {`Download ${selected.size} Items & Merge`}
              </button>
            )}
          </div>
        </>
      )}

      {/* Queued confirmation */}
      {phase === "queued" && (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-500/10 flex items-center justify-center">
            <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-xl font-semibold mb-2">Jobs Queued</p>
          <p className="text-sm text-[var(--muted)] mb-6">
            {selected.size} download{selected.size !== 1 ? "s" : ""} added to the queue
          </p>
          <div className="flex gap-3 justify-center">
            <a href="/jobs" className="px-5 py-2.5 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm font-medium hover:bg-[var(--card-border)] transition-colors">
              View Jobs
            </a>
            <button
              onClick={() => { setPhase("input"); setUrl(""); setSource(null); setEntries([]); setSelected(new Set()); }}
              className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
            >
              Download More
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
