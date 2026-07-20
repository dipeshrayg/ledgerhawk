import { Fragment, useState } from "react";
import { useParams } from "react-router-dom";
import { LineChart, Line, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "../components/Badge";
import { Breadcrumb } from "../components/Breadcrumb";
import { Empty, ErrorState, Loading } from "../components/States";
import { StatCard } from "../components/StatCard";
import { api, fmtMoney } from "../lib/api";
import { useApi } from "../lib/useApi";

const TABS = ["CI History", "Rule Inspector", "Forecast", "Contract Tests", "Negotiate"];

export function VendorDetail() {
  const { vendorId } = useParams();
  const [tab, setTab] = useState(TABS[0]);
  const { data: vendor, error: vendorError, loading: vendorLoading } = useApi(() => api.vendor(vendorId), [vendorId]);

  if (vendorLoading) return <Loading label="Loading vendor…" />;
  if (vendorError) return <ErrorState message={vendorError} />;

  return (
    <div className="space-y-6">
      <div>
        <Breadcrumb trail={[{ label: "Dashboard", to: "/app" }, { label: vendor.vendor_name }]} />
        <h1 className="text-2xl font-bold">{vendor.vendor_name}</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">{vendor.category} · {vendor.ast.documents.length} document(s)</p>
      </div>

      <div className="flex gap-1 border-b border-neutral-200 dark:border-neutral-800">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium ${
              tab === t
                ? "border-b-2 border-indigo-600 text-indigo-600 dark:text-indigo-400"
                : "text-neutral-500 hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-200"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "CI History" && <CIHistoryTab vendorId={vendorId} />}
      {tab === "Rule Inspector" && <RuleInspectorTab vendorId={vendorId} />}
      {tab === "Forecast" && <ForecastTab vendorId={vendorId} />}
      {tab === "Contract Tests" && <ContractTestsTab vendorId={vendorId} />}
      {tab === "Negotiate" && <NegotiateTab vendorId={vendorId} />}
    </div>
  );
}

function CIHistoryTab({ vendorId }) {
  const { data, error, loading } = useApi(() => api.ciHistory(vendorId), [vendorId]);
  const [expanded, setExpanded] = useState(null);
  const [letters, setLetters] = useState({});

  if (loading) return <Loading label="Running Contract CI…" />;
  if (error) return <ErrorState message={error} />;

  async function loadLetter(invoiceId) {
    if (letters[invoiceId]) return setExpanded(invoiceId);
    const res = await api.disputeLetter(vendorId, invoiceId);
    setLetters((l) => ({ ...l, [invoiceId]: res.letter }));
    setExpanded(invoiceId);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium">Build status:</span>
        <Badge kind={data.build_status}>{data.build_status}</Badge>
        <span className="text-sm text-neutral-500 dark:text-neutral-400">
          Contract tests: {data.contract_tests.pass_count}/{data.contract_tests.pass_count + data.contract_tests.fail_count} passing
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-neutral-50 text-left text-xs uppercase text-neutral-500 dark:bg-neutral-900 dark:text-neutral-400">
            <tr>
              <th className="px-3 py-2">Invoice</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Expected</th>
              <th className="px-3 py-2">Billed</th>
              <th className="px-3 py-2">Delta</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {data.history.map((h) => (
              <Fragment key={h.invoice_id}>
                <tr className="border-t border-neutral-100 dark:border-neutral-800">
                  <td className="mono px-3 py-2">{h.invoice_id}</td>
                  <td className="px-3 py-2"><Badge kind={h.status}>{h.status}</Badge></td>
                  <td className="px-3 py-2">{fmtMoney(h.expected_total)}</td>
                  <td className="px-3 py-2">{fmtMoney(h.actual_total)}</td>
                  <td className={`px-3 py-2 font-medium ${h.status === "FAIL" ? "text-red-600 dark:text-red-400" : ""}`}>
                    {h.status === "FAIL" ? `+${fmtMoney(h.delta)}` : " - "}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {h.status === "FAIL" && (
                      <button onClick={() => loadLetter(h.invoice_id)} className="text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400">
                        {expanded === h.invoice_id ? "Hide evidence" : "View evidence →"}
                      </button>
                    )}
                  </td>
                </tr>
                {expanded === h.invoice_id && letters[h.invoice_id] && (
                  <tr>
                    <td colSpan={6} className="border-t border-neutral-100 bg-neutral-50 px-4 py-3 dark:border-neutral-800 dark:bg-neutral-900">
                      <pre className="whitespace-pre-wrap font-sans text-sm">{letters[h.invoice_id]}</pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RuleInspectorTab({ vendorId }) {
  const { data, error, loading } = useApi(() => api.ruleInspector(vendorId), [vendorId]);
  if (loading) return <Loading label="Resolving effective terms…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-3">
      <p className="text-sm text-neutral-500 dark:text-neutral-400">Effective terms as of {data.as_of} - trust through transparency: every rule shows which document it came from.</p>
      {data.effective_terms.length === 0 ? (
        <Empty message="No effective rules." />
      ) : (
        data.effective_terms.map((t) => (
          <div key={t.rule_key} className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
            <div className="flex items-center justify-between">
              <span className="mono text-sm font-semibold">{t.rule_key}</span>
              <Badge kind="neutral">{t.rule_type}</Badge>
            </div>
            <p className="mt-2 text-sm">
              {Object.entries(t.params).map(([k, v]) => (
                <span key={k} className="mr-3"><span className="text-neutral-500 dark:text-neutral-400">{k}:</span> {String(v)}</span>
              ))}
            </p>
            <p className="mt-2 text-xs italic text-neutral-500 dark:text-neutral-400">"{t.provenance_quote}"</p>
            <p className="mt-1 text-xs text-indigo-600 dark:text-indigo-400">from {t.source_name} (§{t.provenance_section}), effective {t.effective_from}{t.effective_to ? ` – ${t.effective_to}` : ""}</p>
            {t.superseded_rule_ids.length > 0 && (
              <p className="mt-1 text-xs text-neutral-400">supersedes: {t.superseded_rule_ids.join(", ")}</p>
            )}
          </div>
        ))
      )}
    </div>
  );
}

function ForecastTab({ vendorId }) {
  const { data, error, loading } = useApi(() => api.forecast(vendorId, 36), [vendorId]);
  if (loading) return <Loading label="Replaying 36 months forward…" />;
  if (error) return <ErrorState message={error} />;

  const chartData = data.series.map((s) => ({ month: s.period_start.slice(0, 7), total: parseFloat(s.total) }));

  return (
    <div className="space-y-4">
      {data.headline ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm font-medium text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          {data.headline}
        </div>
      ) : (
        <Empty message="No projected cost increase found - this contract is flat over the forecast window." />
      )}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <StatCard label="Month 1 cost" value={fmtMoney(data.start_total)} />
        <StatCard label="Month 36 cost" value={fmtMoney(data.end_total)} />
        {data.annualized_impact && <StatCard label="Annualized impact" value={fmtMoney(data.annualized_impact)} tone="bad" />}
      </div>
      <div className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
        <ResponsiveContainer width="100%" height={280} aria-label="Line chart of 36-month cost forecast">
          <LineChart data={chartData} accessibilityLayer>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} interval={2} />
            <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
            <Tooltip formatter={(v) => fmtMoney(v)} />
            <Line type="stepAfter" dataKey="total" stroke="#4f46e5" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
        <table className="sr-only">
          <caption>36-month forecast, monthly projected cost</caption>
          <thead><tr><th>Month</th><th>Projected cost</th></tr></thead>
          <tbody>
            {chartData.map((row) => (
              <tr key={row.month}><td>{row.month}</td><td>{fmtMoney(row.total)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-neutral-500 dark:text-neutral-400">
        No ML here - this is deterministic contract replay: the same compiled DSL, held at today's usage baseline, walked forward 36 months.
      </p>
    </div>
  );
}

function ContractTestsTab({ vendorId }) {
  const { data, error, loading } = useApi(() => api.contractTests(vendorId), [vendorId]);
  if (loading) return <Loading label="Running contract tests…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-sm">
        <Badge kind={data.all_passed ? "PASS" : "FAIL"}>{data.all_passed ? "ALL PASS" : "FAILURES"}</Badge>
        <span>{data.pass_count} passing / {data.fail_count} failing</span>
      </div>
      <div className="divide-y divide-neutral-100 rounded-lg border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
        {data.results.map((r, i) => (
          <div key={i} className="flex items-center justify-between px-4 py-3 text-sm">
            <div>
              <div className="font-medium">{r.name}</div>
              <div className="text-xs text-neutral-500 dark:text-neutral-400">{r.detail}</div>
            </div>
            <Badge kind={r.status}>{r.status}</Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

function NegotiateTab({ vendorId }) {
  const [negotiation, setNegotiation] = useState(null);
  const [negotiating, setNegotiating] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    setNegotiating(true);
    setError(null);
    try {
      setNegotiation(await api.negotiateVendor(vendorId));
    } catch (e) {
      setError(e.message);
    } finally {
      setNegotiating(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-neutral-500 dark:text-neutral-400">
        Compares this vendor's current terms against the category benchmark and computes a real
        36-month savings estimate by replaying both through the forecast engine (F5).
      </p>
      <button
        onClick={run}
        disabled={negotiating}
        className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {negotiating ? "Generating…" : negotiation ? "Regenerate negotiation email" : "Generate negotiation email"}
      </button>
      {error && <ErrorState message={error} />}
      {negotiation && (
        <div className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
          <div className="flex flex-wrap gap-4 text-sm">
            <span>Risk score: <strong>{negotiation.risk_score}/100</strong></span>
            <span>Expected 36-mo savings: <strong className="text-emerald-600 dark:text-emerald-400">{fmtMoney(negotiation.expected_savings_36mo)}</strong></span>
          </div>
          <ul className="list-disc pl-5 text-sm">
            {negotiation.alternative_terms.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
          <pre className="whitespace-pre-wrap rounded-lg bg-neutral-50 p-3 font-sans text-sm dark:bg-neutral-800">{negotiation.negotiation_email}</pre>
        </div>
      )}
    </div>
  );
}
