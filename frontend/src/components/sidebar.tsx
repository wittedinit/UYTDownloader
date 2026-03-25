"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Download", icon: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" },
  { href: "/jobs", label: "Jobs", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" },
  { href: "/library", label: "Library", icon: "M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" },
  { href: "/search", label: "Search", icon: "M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" },
  { href: "/subscriptions", label: "Subscriptions", icon: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" },
  { href: "/settings", label: "Settings", icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z" },
  { href: "/manual", label: "Manual", icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" },
];

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile menu on navigation
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  // Close on escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMobileOpen(false); };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const navContent = (
    <>
      {/* Logo */}
      <div className="px-5 py-5 border-b border-[var(--card-border)]">
        <Link href="/" className="flex items-center gap-2.5" onClick={() => setMobileOpen(false)}>
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </div>
          <span className="text-[var(--sidebar-active)] font-semibold text-sm tracking-tight">UYTDownloader</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-colors touch-manipulation ${
                isActive
                  ? "bg-indigo-500/15 text-indigo-400"
                  : "text-[var(--sidebar-text)] hover:bg-white/5 hover:text-[var(--sidebar-active)] active:bg-white/10"
              }`}
            >
              <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
              </svg>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-[var(--card-border)]">
        <p className="text-xs text-[var(--sidebar-text)]">v0.2.0</p>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile top bar */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-[var(--sidebar-bg)] border-b border-[var(--card-border)] flex items-center px-4 z-50">
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="p-2 -ml-2 rounded-lg hover:bg-white/5 active:bg-white/10 touch-manipulation"
          aria-label="Toggle menu"
        >
          <svg className="w-6 h-6 text-[var(--sidebar-active)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {mobileOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
        <Link href="/" className="flex items-center gap-2 ml-3" onClick={() => setMobileOpen(false)}>
          <div className="w-7 h-7 rounded-md bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </div>
          <span className="text-[var(--sidebar-active)] font-semibold text-sm">UYTDownloader</span>
        </Link>
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-50" onClick={() => setMobileOpen(false)}>
          <aside
            className="w-64 h-full bg-[var(--sidebar-bg)] flex flex-col shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {navContent}
          </aside>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="hidden lg:flex fixed left-0 top-0 h-screen w-56 bg-[var(--sidebar-bg)] border-r border-[var(--card-border)] flex-col z-50">
        {navContent}
      </aside>
    </>
  );
}
