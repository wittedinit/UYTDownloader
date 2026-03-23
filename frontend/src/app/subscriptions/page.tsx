"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listSubscriptions,
  deleteSubscription,
  triggerSubscriptionCheck,
  updateSubscription,
  type Subscription,
} from "@/lib/api";

export default function SubscriptionsPage() {
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSubs = useCallback(async () => {
    try {
      const res = await listSubscriptions();
      setSubs(res.subscriptions);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSubs();
    const interval = setInterval(fetchSubs, 10000);
    return () => clearInterval(interval);
  }, [fetchSubs]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this subscription?")) return;
    try {
      await deleteSubscription(id);
      fetchSubs();
    } catch {
      // ignore
    }
  };

  const handleCheck = async (id: string) => {
    try {
      await triggerSubscriptionCheck(id);
      alert("Check triggered — results will appear in Jobs");
    } catch {
      alert("Failed to trigger check");
    }
  };

  const handleToggle = async (sub: Subscription) => {
    try {
      await updateSubscription(sub.id, { enabled: !sub.enabled });
      fetchSubs();
    } catch {
      // ignore
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return "Never";
    return new Date(iso).toLocaleString();
  };

  return (
    <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Subscriptions</h1>
        <div className="flex gap-3">
          <a href="/jobs" className="text-sm text-blue-600 hover:underline">Jobs</a>
          <a href="/" className="text-sm text-blue-600 hover:underline">New Download</a>
        </div>
      </div>

      <p className="text-sm text-gray-500 mb-6">
        Subscribe to channels or playlists. New videos matching your filters are downloaded automatically.
      </p>

      {loading ? (
        <p className="text-center py-8 text-gray-500">Loading...</p>
      ) : subs.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">No subscriptions yet</p>
          <p className="text-sm text-gray-400">
            Probe a channel or playlist from the <a href="/" className="text-blue-600 hover:underline">home page</a>,
            then subscribe to it.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {subs.map((sub) => (
            <div
              key={sub.id}
              className={`p-4 border rounded-lg ${sub.enabled ? "border-gray-200 dark:border-gray-700" : "border-gray-100 opacity-60 dark:border-gray-800"}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-medium truncate">{sub.source_title || "Unknown source"}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                      {sub.source_type}
                    </span>
                    {sub.enabled ? (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">Active</span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-200 text-gray-500">Paused</span>
                    )}
                  </div>

                  <div className="text-xs text-gray-500 space-y-0.5">
                    <p>
                      {sub.format_mode} &middot; {sub.quality} &middot; SB: {sub.sponsorblock_action}
                      {sub.auto_download && " \u00b7 auto-download"}
                    </p>
                    <p>
                      Check every {sub.check_interval_minutes}m &middot;
                      Last: {formatDate(sub.last_checked_at)} &middot;
                      Next: {formatDate(sub.next_check_at)}
                    </p>
                    {sub.entry_count != null && (
                      <p>{sub.entry_count} entries tracked</p>
                    )}
                  </div>
                </div>

                <div className="flex gap-1 ml-3 flex-shrink-0">
                  <button
                    onClick={() => handleCheck(sub.id)}
                    className="px-2 py-1 text-xs border rounded hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-800"
                    title="Check now"
                  >
                    Check
                  </button>
                  <button
                    onClick={() => handleToggle(sub)}
                    className={`px-2 py-1 text-xs border rounded ${
                      sub.enabled
                        ? "border-yellow-300 text-yellow-700 hover:bg-yellow-50"
                        : "border-green-300 text-green-700 hover:bg-green-50"
                    }`}
                  >
                    {sub.enabled ? "Pause" : "Resume"}
                  </button>
                  <button
                    onClick={() => handleDelete(sub.id)}
                    className="px-2 py-1 text-xs border border-red-300 text-red-600 rounded hover:bg-red-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
