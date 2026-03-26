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
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("input");
  const [error, setError] = useState("");
  const [source, setSource] = useState<Source | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [formatMode, setFormatMode] = useState("video_audio");
  const [quality, setQuality] = useState("best");
  const [sponsorblock, setSponsorblock] = useState("keep");
  const [embedSubs, setEmbedSubs] = useState(false);
  const [normalizeAudio, setNormalizeAudio] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [outputFormat, setOutputFormat] = useState("original");
  const [videoBitrate, setVideoBitrate] = useState("auto");
  const [hydrated, setHydrated] = useState(false);

  // Restore state from sessionStorage after mount (avoids SSR hydration mismatch)
  useEffect(() => {
    const saved = loadSession();
    if (saved) {
      if (saved.url) setUrl(saved.url as string);
      if (saved.phase && saved.phase !== "probing") setPhase(saved.phase as Phase);
      if (saved.error) setError(saved.error as string);
      if (saved.source) setSource(saved.source as Source);
      if (saved.entries) setEntries(saved.entries as Entry[]);
      if (saved.selected) setSelected(new Set(saved.selected as string[]));
      if (saved.formatMode) setFormatMode(saved.formatMode as string);
      if (saved.quality) setQuality(saved.quality as string);
      if (saved.sponsorblock) setSponsorblock(saved.sponsorblock as string);
      if (saved.embedSubs != null) setEmbedSubs(saved.embedSubs as boolean);
      if (saved.normalizeAudio != null) setNormalizeAudio(saved.normalizeAudio as boolean);
      if (saved.playbackSpeed != null) setPlaybackSpeed(saved.playbackSpeed as number);
      if (saved.outputFormat) setOutputFormat(saved.outputFormat as string);
      if (saved.videoBitrate) setVideoBitrate(saved.videoBitrate as string);
    }
    // Check for ?url= query param (from browser extension handoff)
    const params = new URLSearchParams(window.location.search);
    const extUrl = params.get("url");
    if (extUrl) {
      setUrl(extUrl);
      // Clean the URL param without reload
      window.history.replaceState({}, "", window.location.pathname);
    }
    setHydrated(true);
  }, []);

  // Persist state to sessionStorage on changes (only after hydration)
  useEffect(() => {
    if (!hydrated || phase === "probing") return;
    saveSession({
      url, phase, error, source, entries,
      selected: Array.from(selected),
      formatMode, quality, sponsorblock, embedSubs, normalizeAudio, playbackSpeed,
      outputFormat, videoBitrate,
    });
  }, [hydrated, url, phase, error, source, entries, selected, formatMode, quality, sponsorblock, embedSubs, normalizeAudio, playbackSpeed, outputFormat, videoBitrate]);

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
        playback_speed: playbackSpeed,
        output_format: outputFormat !== "original" ? outputFormat : undefined,
        video_bitrate: videoBitrate !== "auto" ? videoBitrate : undefined,
      });
      setPhase("queued");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create jobs");
      setPhase("error");
    }
  }, [selected, formatMode, quality, sponsorblock, embedSubs, normalizeAudio, playbackSpeed]);

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
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto w-full">
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
            aria-disabled={phase === "probing"}
          />
          <button
            onClick={handleProbe}
            disabled={phase === "probing" || !url.trim()}
            className="px-6 py-3 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {phase === "probing" ? (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                Probing
              </span>
            ) : "Probe"}
          </button>
          {(phase !== "input" || url) && (
            <button
              onClick={() => {
                setUrl(""); setPhase("input"); setError(""); setSource(null);
                setEntries([]); setSelected(new Set()); setFormatMode("video_audio");
                setQuality("best"); setSponsorblock("keep"); setEmbedSubs(false);
                setNormalizeAudio(false); setOutputFormat("original"); setVideoBitrate("auto");
                try { sessionStorage.removeItem("uyt_probe"); } catch {}
              }}
              className="px-4 py-3 border border-[var(--card-border)] text-[var(--muted)] rounded-lg text-sm font-medium hover:text-[var(--foreground)] hover:border-[var(--muted)] transition-colors"
            >
              Reset
            </button>
          )}
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
          <div className="inline-block w-10 h-10 border-3 border-indigo-400/30 border-t-indigo-500 rounded-full animate-spin mb-4" role="status" aria-label="Extracting metadata" />
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

          {/* Quick workflow templates */}
          <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-4 mb-4">
            <h3 className="text-xs font-medium text-[var(--muted)] mb-3 uppercase tracking-wider">Quick Presets</h3>
            <div className="flex flex-wrap gap-2">
              {[
                { label: "Best Quality", desc: "Video+Audio, best, keep sponsors", fm: "video_audio", q: "best", sb: "keep", subs: false, norm: false, of: "original", vb: "auto" },
                { label: "Background Listen", desc: "Audio only, no sponsors, normalized", fm: "audio_only", q: "audio_192k", sb: "remove", subs: false, norm: true, of: "mp3", vb: "auto" },
                { label: "Archive", desc: "Best video+audio, keep all, embed subs", fm: "video_audio", q: "best", sb: "mark_chapters", subs: true, norm: false, of: "original", vb: "auto" },
                { label: "Mobile", desc: "720p video, small size", fm: "video_audio", q: "720p", sb: "remove", subs: false, norm: false, of: "mp4_h264", vb: "3000" },
                { label: "Podcast", desc: "Audio 128k, no sponsors, normalized", fm: "audio_only", q: "audio_128k", sb: "remove", subs: false, norm: true, of: "mp3", vb: "auto" },
              ].map((t) => (
                <button key={t.label} title={t.desc}
                  onClick={() => { setFormatMode(t.fm); setQuality(t.q); setSponsorblock(t.sb); setEmbedSubs(t.subs); setNormalizeAudio(t.norm); setOutputFormat(t.of); setVideoBitrate(t.vb); }}
                  className="px-3 py-1.5 text-xs font-medium bg-[var(--background)] border border-[var(--card-border)] rounded-lg hover:border-indigo-500/50 hover:text-indigo-400 transition-colors touch-manipulation">
                  {t.label}
                </button>
              ))}
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
                    disabled={outputFormat === "original"}
                    aria-disabled={outputFormat === "original"}>
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
              <div className="flex items-center gap-2 text-sm">
                <span className="text-[var(--muted)]">Speed:</span>
                <select value={playbackSpeed} onChange={(e) => setPlaybackSpeed(parseFloat(e.target.value))}
                  className="px-2 py-1 bg-[var(--background)] border border-[var(--card-border)] rounded text-sm focus:ring-2 focus:ring-indigo-500">
                  <option value={1.0}>1x (Normal)</option>
                  <option value={1.25}>1.25x</option>
                  <option value={1.5}>1.5x</option>
                  <option value={1.75}>1.75x</option>
                  <option value={2.0}>2x</option>
                </select>
              </div>
            </div>
          </div>

          {/* Entries card */}
          <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl overflow-hidden mb-6">
            <div className="px-5 py-3 border-b border-[var(--card-border)] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button onClick={toggleAll} className="text-sm text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
                  {selected.size === entries.length ? "Deselect All" : "Select All"}
                </button>
                {selected.size >= 2 && (
                  <span className="text-xs text-[var(--muted)] bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded">
                    Drag to reorder for merge
                  </span>
                )}
              </div>
              <span className="text-sm text-[var(--muted)]">{selected.size} of {entries.length} selected</span>
            </div>
            <div className="max-h-[500px] overflow-y-auto">
              {entries.map((entry, index) => (
                <div
                  key={entry.id}
                  draggable
                  onDragStart={(e) => { e.dataTransfer.setData("text/plain", String(index)); e.currentTarget.classList.add("opacity-50"); }}
                  onDragEnd={(e) => { e.currentTarget.classList.remove("opacity-50"); }}
                  onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("border-t-2", "border-t-indigo-500"); }}
                  onDragLeave={(e) => { e.currentTarget.classList.remove("border-t-2", "border-t-indigo-500"); }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.currentTarget.classList.remove("border-t-2", "border-t-indigo-500");
                    const fromIdx = parseInt(e.dataTransfer.getData("text/plain"));
                    const toIdx = index;
                    if (fromIdx !== toIdx) {
                      const newEntries = [...entries];
                      const [moved] = newEntries.splice(fromIdx, 1);
                      newEntries.splice(toIdx, 0, moved);
                      setEntries(newEntries);
                    }
                  }}
                  className={`flex items-start gap-4 px-5 py-3.5 cursor-grab active:cursor-grabbing transition-colors border-b border-[var(--card-border)] last:border-b-0 ${
                    selected.has(entry.id) ? "bg-indigo-500/5" : "hover:bg-[var(--background)]"
                  }`}
                >
                  {/* Drag handle + checkbox */}
                  <div className="flex items-center gap-2 pt-1 flex-shrink-0">
                    <svg className="w-4 h-4 text-[var(--muted)] opacity-40" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M7 2a2 2 0 10.001 4.001A2 2 0 007 2zm0 6a2 2 0 10.001 4.001A2 2 0 007 8zm0 6a2 2 0 10.001 4.001A2 2 0 007 14zm6-8a2 2 0 10-.001-4.001A2 2 0 0013 6zm0 2a2 2 0 10.001 4.001A2 2 0 0013 8zm0 6a2 2 0 10.001 4.001A2 2 0 0013 14z" />
                    </svg>
                    <input
                      type="checkbox"
                      checked={selected.has(entry.id)}
                      onChange={() => toggleEntry(entry.id)}
                      aria-label={`Select ${entry.title}`}
                      className="w-4 h-4 rounded border-[var(--card-border)] text-indigo-600 focus:ring-indigo-500"
                    />
                  </div>

                  {/* Thumbnail */}
                  {entry.thumbnail_url && (
                    <img src={entry.thumbnail_url} alt="" className="w-28 h-16 rounded-lg object-cover flex-shrink-0" />
                  )}

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold truncate mb-2">{entry.title}</p>
                    <div className="flex flex-wrap gap-2">
                      {source?.uploader && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-gradient-to-r from-blue-600/20 to-cyan-600/20 text-cyan-300 border border-cyan-500/20">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                          {source.uploader}
                        </span>
                      )}
                      {entry.upload_date && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-gradient-to-r from-violet-600/20 to-purple-600/20 text-purple-300 border border-purple-500/20">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                          {entry.upload_date.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3")}
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-gradient-to-r from-emerald-600/20 to-green-600/20 text-emerald-300 border border-emerald-500/20">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        {formatDuration(entry.duration)}
                      </span>
                    </div>
                  </div>

                  {/* Position number */}
                  <span className="text-xs text-[var(--muted)] opacity-40 font-mono pt-1 flex-shrink-0">#{index + 1}</span>
                </div>
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
            <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
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
