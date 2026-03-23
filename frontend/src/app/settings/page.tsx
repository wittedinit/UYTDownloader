"use client";

import { useState, useEffect, useCallback } from "react";
import { getDiskUsage, getStoragePresets, runRetention, runDiskGuard, getHealth, type DiskUsage } from "@/lib/api";

export default function SettingsPage() {
  const [usage, setUsage] = useState<DiskUsage | null>(null);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [presets, setPresets] = useState<{
    retention_presets: { key: string; label: string; is_forever: boolean }[];
    cleanup_strategies: { key: string; description: string }[];
  } | null>(null);

  const [retention, setRetention] = useState("forever");
  const [diskGuardPct, setDiskGuardPct] = useState(10);
  const [diskGuardStrategy, setDiskGuardStrategy] = useState("oldest_first");
  const [result, setResult] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [u, p, h] = await Promise.all([getDiskUsage(), getStoragePresets(), getHealth()]);
      setUsage(u);
      setPresets(p);
      setHealth(h);
    } catch {}
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleRetention = async (dryRun: boolean) => {
    try {
      const res = await runRetention(retention, dryRun);
      const r = res as { count?: number; freed_gb?: number; dry_run?: boolean };
      setResult(`${dryRun ? "Preview" : "Cleaned"}: ${r.count || 0} files, ${r.freed_gb || 0} GB freed`);
      if (!dryRun) fetchData();
    } catch (e) { setResult(`Error: ${e}`); }
  };

  const handleDiskGuard = async (dryRun: boolean) => {
    try {
      const res = await runDiskGuard(diskGuardPct, diskGuardStrategy, dryRun);
      const r = res as { count?: number; freed_gb?: number; disk_free_pct_after?: number; message?: string };
      setResult(r.message || `${dryRun ? "Preview" : "Cleaned"}: ${r.count || 0} files, ${r.freed_gb || 0} GB freed`);
      if (!dryRun) fetchData();
    } catch (e) { setResult(`Error: ${e}`); }
  };

  const usedPct = usage ? ((usage.disk_used_gb / usage.disk_total_gb) * 100) : 0;

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Settings</h1>
        <p className="text-sm text-[var(--muted)]">Storage management, system health, and configuration</p>
      </div>

      {/* Disk Usage */}
      {usage && (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-6 mb-6">
          <h2 className="text-xs font-medium text-[var(--muted)] mb-4 uppercase tracking-wider">Disk Usage</h2>
          <div className="mb-4">
            <div className="flex justify-between text-sm mb-2">
              <span>{usage.disk_used_gb} GB used</span>
              <span>{usage.disk_free_gb} GB free ({usage.disk_free_pct}%)</span>
            </div>
            <div className="h-3 bg-[var(--background)] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${usedPct > 90 ? "bg-red-500" : usedPct > 70 ? "bg-amber-500" : "bg-indigo-500"}`}
                style={{ width: `${usedPct}%` }}
              />
            </div>
            <p className="text-xs text-[var(--muted)] mt-2">{usage.disk_total_gb} GB total</p>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-3 bg-[var(--background)] rounded-lg text-center">
              <p className="text-xl font-bold">{usage.downloads_file_count}</p>
              <p className="text-xs text-[var(--muted)]">Files</p>
            </div>
            <div className="p-3 bg-[var(--background)] rounded-lg text-center">
              <p className="text-xl font-bold">{usage.downloads_gb} GB</p>
              <p className="text-xs text-[var(--muted)]">Downloads</p>
            </div>
            <div className="p-3 bg-[var(--background)] rounded-lg text-center">
              <p className="text-xl font-bold">{usage.disk_free_pct}%</p>
              <p className="text-xs text-[var(--muted)]">Free Space</p>
            </div>
          </div>
        </div>
      )}

      {/* Retention Policy */}
      <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-6 mb-6">
        <h2 className="text-xs font-medium text-[var(--muted)] mb-1 uppercase tracking-wider">Retention Policy</h2>
        <p className="text-xs text-[var(--muted)] mb-4">Runs automatically every hour. Deletes files older than the selected period.</p>
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-xs text-[var(--muted)] mb-1.5">Delete files older than</label>
            <select value={retention} onChange={(e) => setRetention(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
              {presets?.retention_presets.map((p) => (
                <option key={p.key} value={p.key}>{p.label}</option>
              )) || <option value="forever">Forever</option>}
            </select>
          </div>
          <button onClick={() => handleRetention(true)}
            className="px-4 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm font-medium hover:border-[var(--muted)] transition-colors">
            Preview What Would Be Deleted
          </button>
          <button onClick={() => { if (confirm(`This will permanently delete all files older than "${retention.replace(/_/g, " ")}". Continue?`)) handleRetention(false); }} disabled={retention === "forever"}
            className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 disabled:opacity-40 transition-colors">
            Run Cleanup Now
          </button>
        </div>
        {retention === "forever" && (
          <p className="text-xs text-emerald-400 mt-3">Retention is set to forever — files are never auto-deleted.</p>
        )}
      </div>

      {/* Disk Space Guard */}
      <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-6 mb-6">
        <h2 className="text-xs font-medium text-[var(--muted)] mb-1 uppercase tracking-wider">Disk Space Guard</h2>
        <p className="text-xs text-[var(--muted)] mb-4">
          Checked automatically every hour. If free disk space is below the threshold, files are deleted using the chosen strategy until space is recovered.
          {usage && <span className="text-[var(--foreground)]"> Currently {usage.disk_free_pct}% free.</span>}
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs text-[var(--muted)] mb-1.5">Minimum free space (%)</label>
            <input type="number" value={diskGuardPct} onChange={(e) => setDiskGuardPct(Number(e.target.value))}
              min={1} max={50}
              className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          <div>
            <label className="block text-xs text-[var(--muted)] mb-1.5">Cleanup strategy</label>
            <select value={diskGuardStrategy} onChange={(e) => setDiskGuardStrategy(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
              {presets?.cleanup_strategies.map((s) => (
                <option key={s.key} value={s.key}>{s.key.replace(/_/g, " ")} — {s.description}</option>
              )) || <>
                <option value="oldest_first">Oldest first</option>
                <option value="newest_first">Newest first</option>
                <option value="largest_first">Largest first</option>
                <option value="smallest_first">Smallest first</option>
              </>}
            </select>
          </div>
        </div>
        <div className="flex gap-3">
          <button onClick={() => handleDiskGuard(true)}
            className="px-4 py-2 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm font-medium hover:border-[var(--muted)] transition-colors">
            Preview What Would Be Deleted
          </button>
          <button onClick={() => { if (confirm(`If free space is below ${diskGuardPct}%, this will delete files (${diskGuardStrategy.replace(/_/g, " ")}) until space is recovered. Continue?`)) handleDiskGuard(false); }}
            className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors">
            Run Guard Now
          </button>
        </div>
        {usage && usage.disk_free_pct >= diskGuardPct && (
          <p className="text-xs text-emerald-400 mt-3">Disk has {usage.disk_free_pct}% free — above the {diskGuardPct}% threshold. No cleanup needed.</p>
        )}
        {usage && usage.disk_free_pct < diskGuardPct && (
          <p className="text-xs text-amber-400 mt-3">Disk has {usage.disk_free_pct}% free — below the {diskGuardPct}% threshold. Files will be deleted on next automatic check.</p>
        )}
      </div>

      {/* Result message */}
      {result && (
        <div className="mb-6 p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-sm text-indigo-300 flex justify-between items-center">
          <span>{result}</span>
          <button onClick={() => setResult(null)} className="text-indigo-400 hover:text-white">&times;</button>
        </div>
      )}

      {/* System Health */}
      {health && (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-6">
          <h2 className="text-xs font-medium text-[var(--muted)] mb-4 uppercase tracking-wider">System Health</h2>
          <div className="space-y-2 text-sm">
            {Object.entries((health as { checks?: Record<string, unknown> }).checks || {}).map(([key, value]) => {
              if (typeof value === "object" && value !== null) return null;
              const isOk = value === "ok" || (typeof value === "string" && !value.toString().includes("error"));
              return (
                <div key={key} className="flex justify-between py-1.5 border-b border-[var(--card-border)] last:border-0">
                  <span className="text-[var(--muted)]">{key}</span>
                  <span className={isOk ? "text-emerald-400" : "text-red-400"}>
                    {typeof value === "string" ? (value.length > 40 ? value.slice(0, 40) + "..." : value) : String(value)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
