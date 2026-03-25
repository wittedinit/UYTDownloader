"use client";

import { useState, useRef, useEffect } from "react";
import { apiFetch, resolveApiBase } from "@/lib/api";

interface SearchResult {
  id: string;
  video_id: string;
  title: string;
  channel: string;
  language: string;
  rank: number;
  snippet: string;
}

interface SearchStats {
  indexed_videos: number;
  total_characters: number;
  estimated_hours: number;
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [stats, setStats] = useState<SearchStats | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const apiBase = resolveApiBase();

  useEffect(() => {
    apiFetch<SearchStats>("/api/search/stats").then(setStats).catch(() => {});
    inputRef.current?.focus();
  }, []);

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearched(true);
    try {
      const res = await apiFetch<{ results: SearchResult[]; total: number }>(
        `/api/search?q=${encodeURIComponent(query.trim())}&limit=50`
      );
      setResults(res.results);
      setTotal(res.total);
    } catch {
      setResults([]);
      setTotal(0);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Search Transcripts</h1>
        <p className="text-sm text-[var(--muted)]">
          Find videos by what was said in them
          {stats && stats.indexed_videos > 0 && (
            <span> &middot; {stats.indexed_videos} videos indexed ({stats.estimated_hours}h of content)</span>
          )}
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="mb-8">
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-4 flex gap-3">
          <div className="relative flex-1">
            <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              placeholder="Search across all downloaded video transcripts..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-[var(--background)] border border-[var(--card-border)] rounded-xl text-base focus:outline-none focus:border-indigo-500/50 transition-colors"
            />
          </div>
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl font-medium hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 transition-all"
          >
            {searching ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      {/* Results */}
      {!searched && stats && stats.indexed_videos === 0 && (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center">
          <svg className="w-16 h-16 mx-auto mb-4 text-[var(--muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <h2 className="text-lg font-semibold mb-2">No transcripts indexed yet</h2>
          <p className="text-sm text-[var(--muted)] max-w-md mx-auto">
            Transcripts are automatically indexed when videos are downloaded. Download some videos first, then search across their content here.
          </p>
        </div>
      )}

      {searched && results.length === 0 && !searching && (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center text-[var(--muted)]">
          No results found for &ldquo;{query}&rdquo;
        </div>
      )}

      {results.length > 0 && (
        <>
          <p className="text-sm text-[var(--muted)] mb-4">{total} result{total !== 1 ? "s" : ""} found</p>
          <div className="space-y-3">
            {results.map((r) => (
              <div key={r.id} className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-5 hover:border-indigo-500/30 transition-colors">
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold truncate">{r.title || r.video_id}</h3>
                    <p className="text-xs text-[var(--muted)] mt-0.5">
                      {r.channel && <span>{r.channel} &middot; </span>}
                      <span>{r.language.toUpperCase()}</span>
                    </p>
                  </div>
                  <a
                    href={`https://www.youtube.com/watch?v=${r.video_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 text-xs font-medium bg-[var(--background)] border border-[var(--card-border)] rounded-lg hover:border-[var(--muted)] transition-colors flex-shrink-0"
                  >
                    YouTube
                  </a>
                </div>
                {/* Snippet with highlights */}
                <p
                  className="text-sm text-[var(--muted)] leading-relaxed"
                  dangerouslySetInnerHTML={{
                    __html: r.snippet
                      .replace(/\*\*/g, (_, i) => (i % 2 === 0 ? '<mark class="bg-indigo-500/20 text-indigo-300 px-0.5 rounded">' : "</mark>"))
                      .replace(/\*\*([^*]+)\*\*/g, '<mark class="bg-indigo-500/20 text-indigo-300 px-0.5 rounded">$1</mark>'),
                  }}
                />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
