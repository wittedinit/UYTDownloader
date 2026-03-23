"use client";

import { useState, useEffect, useCallback } from "react";
import { listSubscriptions, deleteSubscription, triggerSubscriptionCheck, updateSubscription, type Subscription } from "@/lib/api";

export default function SubscriptionsPage() {
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSubs = useCallback(async () => {
    try { const res = await listSubscriptions(); setSubs(res.subscriptions); }
    catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchSubs(); const i = setInterval(fetchSubs, 10000); return () => clearInterval(i); }, [fetchSubs]);

  const handleDelete = async (id: string) => { if (!confirm("Delete this subscription?")) return; try { await deleteSubscription(id); fetchSubs(); } catch {} };
  const handleCheck = async (id: string) => { try { await triggerSubscriptionCheck(id); alert("Check triggered"); } catch { alert("Failed"); } };
  const handleToggle = async (sub: Subscription) => { try { await updateSubscription(sub.id, { enabled: !sub.enabled }); fetchSubs(); } catch {} };

  const formatDate = (iso: string | null) => iso ? new Date(iso).toLocaleString() : "Never";

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Subscriptions</h1>
        <p className="text-sm text-[var(--muted)]">Auto-download new content from channels and playlists</p>
      </div>

      {loading ? (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center text-[var(--muted)]">Loading...</div>
      ) : subs.length === 0 ? (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center">
          <p className="text-[var(--muted)] mb-3">No subscriptions yet</p>
          <p className="text-sm text-[var(--muted)]">
            Probe a channel or playlist from the <a href="/" className="text-indigo-400 hover:text-indigo-300">Download</a> page, then click Subscribe.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {subs.map((sub) => (
            <div key={sub.id}
              className={`bg-[var(--card)] border rounded-xl p-5 transition-colors ${sub.enabled ? "border-[var(--card-border)]" : "border-[var(--card-border)] opacity-50"}`}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-semibold truncate">{sub.source_title || "Unknown source"}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 font-medium">{sub.source_type}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-md font-medium ${sub.enabled ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-500/10 text-slate-400"}`}>
                      {sub.enabled ? "Active" : "Paused"}
                    </span>
                  </div>
                  <div className="text-xs text-[var(--muted)] space-y-1">
                    <p>{sub.format_mode} &middot; {sub.quality} &middot; SB: {sub.sponsorblock_action}{sub.auto_download && " \u00b7 auto-download"}</p>
                    <p>Every {sub.check_interval_minutes}m &middot; Last: {formatDate(sub.last_checked_at)} &middot; Next: {formatDate(sub.next_check_at)}</p>
                    {sub.entry_count != null && <p>{sub.entry_count} entries</p>}
                  </div>
                </div>
                <div className="flex gap-2 ml-4">
                  <button onClick={() => handleCheck(sub.id)} className="px-3 py-1.5 text-xs font-medium bg-[var(--background)] border border-[var(--card-border)] rounded-lg hover:border-[var(--muted)] transition-colors">Check</button>
                  <button onClick={() => handleToggle(sub)}
                    className={`px-3 py-1.5 text-xs font-medium border rounded-lg transition-colors ${sub.enabled ? "border-amber-500/30 text-amber-400 hover:bg-amber-500/10" : "border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"}`}>
                    {sub.enabled ? "Pause" : "Resume"}
                  </button>
                  <button onClick={() => handleDelete(sub.id)} className="px-3 py-1.5 text-xs font-medium border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors">Delete</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
