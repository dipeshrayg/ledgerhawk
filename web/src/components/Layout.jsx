import { NavLink, Outlet } from "react-router-dom";
import { useState } from "react";
import { CopilotDrawer } from "./CopilotDrawer";

const NAV = [
  { to: "/app", label: "Dashboard", end: true },
  { to: "/app/calendar", label: "Calendar" },
  { to: "/app/diff/datavault", label: "Version Diff" },
  { to: "/app/presign/talentbridge_proposal", label: "Pre-Sign Review" },
];

function navLinkClass({ isActive }) {
  return `rounded-md px-3 py-1.5 text-sm font-medium transition ${
    isActive
      ? "bg-indigo-600 text-white"
      : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
  }`;
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-indigo-600 focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to main content
      </a>
      <header className="sticky top-0 z-20 border-b border-neutral-200 bg-white/90 backdrop-blur dark:border-neutral-800 dark:bg-neutral-950/90">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-8">
            <NavLink to="/" end className="font-bold text-lg tracking-tight">
              LedgerHawk
            </NavLink>
            <nav className="hidden gap-1 md:flex">
              {NAV.map((n) => (
                <NavLink key={n.to} to={n.to} end={n.end} className={navLinkClass}>
                  {n.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <button
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="Toggle navigation menu"
            className="rounded-md p-2 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800 md:hidden"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              {menuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
        {menuOpen && (
          <nav className="flex flex-col gap-1 border-t border-neutral-200 px-4 py-3 dark:border-neutral-800 md:hidden">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={navLinkClass} onClick={() => setMenuOpen(false)}>
                {n.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>

      <main id="main-content" className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-neutral-200 px-4 py-6 text-center text-xs text-neutral-500 dark:border-neutral-800 dark:text-neutral-400">
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
          <NavLink to="/terms" className="hover:underline">Terms</NavLink>
          <NavLink to="/privacy" className="hover:underline">Privacy</NavLink>
          <NavLink to="/cookies" className="hover:underline">Cookies</NavLink>
          <a href="https://github.com/dipeshrayg/ledgerhawk" className="hover:underline">GitHub</a>
        </div>
      </footer>

      <CopilotDrawer />
    </div>
  );
}
