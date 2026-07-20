import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, DaysBadge } from "../components/Badge";
import { Empty, ErrorState, Loading } from "../components/States";
import { StatCard } from "../components/StatCard";
import { api, fmtMoney, fmtNum } from "../lib/api";
import { useApi } from "../lib/useApi";

const RANK_COLORS = ["#dc2626", "#ea580c", "#d97706", "#65a30d", "#16a34a"];

export function Dashboard() {
  const { data, error, loading } = useApi(api.dashboard, []);

  if (loading) return <Loading label="Loading CFO dashboard…" />;
  if (error) return <ErrorState message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">CFO Dashboard</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          Contracts compiled into executable pricing rules. Invoices are test runs. Overcharges are failing tests.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Recovered leakage" value={fmtMoney(data.total_recovered)} tone="bad" sub={`${data.failing_invoices} failing invoice(s)`} />
        <StatCard label="Compliance rate" value={`${fmtNum(data.compliance_pct)}%`} tone="good" sub={`${data.total_invoices - data.failing_invoices}/${data.total_invoices} invoices passing`} />
        <StatCard label="Forecasted 12-mo leakage" value={fmtMoney(data.forecasted_12mo_leakage_delta)} sub="Scheduled escalations, expiries, uplifts" />
        <StatCard label="Vendors monitored" value={data.vendor_count} sub={`${data.upcoming_renewals_90d.length} renewal(s) in next 90 days`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="mb-3 font-semibold">Vendor risk ranking</h2>
          {data.vendor_risk_ranking.length === 0 ? (
            <Empty message="No vendors have findings." />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220} aria-label="Bar chart of recovered leakage by vendor">
                <BarChart data={data.vendor_risk_ranking} layout="vertical" margin={{ left: 24 }} accessibilityLayer>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                  <YAxis type="category" dataKey="vendor_name" width={140} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v) => fmtMoney(v)} />
                  <Bar dataKey="total_delta" radius={[0, 4, 4, 0]}>
                    {data.vendor_risk_ranking.map((_, i) => (
                      <Cell key={i} fill={RANK_COLORS[i % RANK_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {/* Recharts' accessibilityLayer covers keyboard nav; this table is the
                  screen-reader-native fallback so the same data is a real table, not just an SVG. */}
              <table className="sr-only">
                <caption>Recovered leakage by vendor</caption>
                <thead><tr><th>Vendor</th><th>Total delta</th></tr></thead>
                <tbody>
                  {data.vendor_risk_ranking.map((v) => (
                    <tr key={v.vendor_id}><td>{v.vendor_name}</td><td>{fmtMoney(v.total_delta)}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>

        <section className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
          <h2 className="mb-3 font-semibold">Top violating clauses</h2>
          {data.top_violating_clauses.length === 0 ? (
            <Empty message="No clause-level losses found." />
          ) : (
            <ul className="space-y-3">
              {data.top_violating_clauses.map((c) => (
                <li key={c.rule_key} className="border-b border-neutral-100 pb-2 last:border-0 dark:border-neutral-800">
                  <div className="flex items-center justify-between text-sm font-medium">
                    <span className="mono">{c.rule_key}</span>
                    <span className="text-red-600 dark:text-red-400">{fmtMoney(c.total_delta)}</span>
                  </div>
                  <p className="mt-1 text-xs italic text-neutral-500 dark:text-neutral-400">"{c.clause_quote}"</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Upcoming renewals (next 90 days)</h2>
          <Link to="/app/calendar" className="text-sm text-indigo-600 hover:underline dark:text-indigo-400">Full calendar →</Link>
        </div>
        {data.upcoming_renewals_90d.length === 0 ? (
          <Empty message="No renewals in the next 90 days." />
        ) : (
          <div className="divide-y divide-neutral-100 dark:divide-neutral-800">
            {data.upcoming_renewals_90d.map((r) => (
              <div key={r.vendor_id} className="flex items-center justify-between py-2 text-sm">
                <Link to={`/app/vendors/${r.vendor_id}`} className="font-medium hover:underline">{r.vendor_name}</Link>
                <div className="flex items-center gap-3">
                  <span className="text-neutral-500 dark:text-neutral-400">{r.renewal_date}</span>
                  {r.auto_renewal_uplift_pct && <Badge kind="high">+{r.auto_renewal_uplift_pct}% uplift</Badge>}
                  <DaysBadge days={r.days_remaining} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="mb-3 font-semibold">All vendors</h2>
        <VendorGrid />
      </section>
    </div>
  );
}

function VendorGrid() {
  const { data, error, loading } = useApi(api.vendors, []);
  if (loading) return <Loading label="Loading vendors…" />;
  if (error) return <ErrorState message={error} />;
  return (
    <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-5">
      {data.vendors.map((v) => (
        <Link
          key={v.vendor_id}
          to={`/app/vendors/${v.vendor_id}`}
          className="rounded-lg border border-neutral-200 p-3 transition hover:border-indigo-400 hover:shadow-sm dark:border-neutral-800"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium">{v.vendor_name}</span>
            <Badge kind={v.build_status === "PASS" ? "PASS" : "FAIL"}>{v.build_status}</Badge>
          </div>
          <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">{v.category}</p>
          <p className="mt-2 text-sm">
            {v.finding_count === 0 ? (
              <span className="text-emerald-600 dark:text-emerald-400">Clean - 0 findings</span>
            ) : (
              <span className="text-red-600 dark:text-red-400">{v.finding_count} finding(s), {fmtMoney(v.total_recovered)}</span>
            )}
          </p>
        </Link>
      ))}
    </div>
  );
}
