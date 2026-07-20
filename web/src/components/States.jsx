export function Loading({ label = "Loading…" }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center justify-center py-16 text-sm text-neutral-500 dark:text-neutral-400">
      <svg className="mr-2 h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
      {label}
    </div>
  );
}

export function ErrorState({ message }) {
  return (
    <div role="alert" className="rounded-lg border border-red-300 bg-red-50 px-4 py-6 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
      <strong className="block mb-1">Something went wrong</strong>
      {message}
    </div>
  );
}

export function Empty({ message }) {
  return (
    <div className="rounded-lg border border-dashed border-neutral-300 px-4 py-10 text-center text-sm text-neutral-500 dark:border-neutral-700 dark:text-neutral-400">
      {message}
    </div>
  );
}
