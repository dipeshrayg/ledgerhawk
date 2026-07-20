const STYLES = {
  PASS: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  FAIL: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  high: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  low: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
  neutral: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
};

export function Badge({ children, kind = "neutral" }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLES[kind] || STYLES.neutral}`}>
      {children}
    </span>
  );
}

export function DaysBadge({ days }) {
  let kind = "neutral";
  if (days <= 30) kind = "high";
  else if (days <= 60) kind = "medium";
  return <Badge kind={kind}>{days}d</Badge>;
}
