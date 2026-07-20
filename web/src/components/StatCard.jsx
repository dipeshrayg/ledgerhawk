export function StatCard({ label, value, sub, tone = "default" }) {
  const toneClass = {
    default: "text-neutral-900 dark:text-neutral-50",
    good: "text-emerald-600 dark:text-emerald-400",
    bad: "text-red-600 dark:text-red-400",
  }[tone];

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <div className="text-xs font-medium uppercase tracking-wide text-neutral-500 dark:text-neutral-400">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${toneClass}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">{sub}</div>}
    </div>
  );
}
