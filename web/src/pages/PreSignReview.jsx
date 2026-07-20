import { useState } from "react";
import { useParams } from "react-router-dom";
import { Badge } from "../components/Badge";
import { Breadcrumb } from "../components/Breadcrumb";
import { Empty, ErrorState, Loading } from "../components/States";
import { StatCard } from "../components/StatCard";
import { api, fmtMoney } from "../lib/api";
import { useApi } from "../lib/useApi";

export function PreSignReview() {
  const { proposalId } = useParams();
  const { data, error, loading } = useApi(() => api.presign(proposalId), [proposalId]);
  const [negotiation, setNegotiation] = useState(null);
  const [negotiating, setNegotiating] = useState(false);

  if (loading) return <Loading label="Running Static Validator + benchmark comparison…" />;
  if (error) return <ErrorState message={error} />;

  async function runNegotiation() {
    setNegotiating(true);
    try {
      const res = await api.negotiateProposal(proposalId);
      setNegotiation(res);
    } finally {
      setNegotiating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Breadcrumb trail={[{ label: "Dashboard", to: "/app" }, { label: "Pre-Sign Review" }]} />
        <h1 className="text-2xl font-bold">Pre-Sign Review - {data.vendor_name}</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">Unsigned proposal · {data.category} · Static Validator + illustrative benchmark comparison</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Risk score" value={`${data.risk_score}/100`} tone={data.risk_score > 40 ? "bad" : "default"} />
        <StatCard label="3-yr projected cost" value={fmtMoney(data.projected_cost_36mo)} />
        <StatCard label="Benchmark-compliant cost" value={fmtMoney(data.benchmark_compliant_cost_36mo)} tone="good" />
        <StatCard label="Est. 3-yr impact" value={fmtMoney(data.estimated_3yr_impact)} tone="bad" />
      </div>

      <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="mb-2 font-semibold">Executive summary</h2>
        <p className="text-sm">{data.summary}</p>
      </div>

      <section>
        <h2 className="mb-3 font-semibold">Risk findings (Static Validator)</h2>
        {data.lints.length === 0 ? (
          <Empty message="No risk findings." />
        ) : (
          <div className="space-y-2">
            {data.lints.map((l, i) => (
              <div key={i} className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800">
                <div className="flex items-center gap-2">
                  <Badge kind={l.severity}>{l.severity}</Badge>
                  <span className="font-medium text-sm">{l.message}</span>
                </div>
                <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">{l.explanation}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 font-semibold">Contract unit tests</h2>
        <div className="mb-2 flex items-center gap-3 text-sm">
          <Badge kind={data.contract_tests.all_passed ? "PASS" : "FAIL"}>{data.contract_tests.all_passed ? "ALL PASS" : "FAILURES"}</Badge>
          <span>{data.contract_tests.pass_count} passing / {data.contract_tests.fail_count} failing</span>
        </div>
        <div className="divide-y divide-neutral-100 rounded-lg border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
          {data.contract_tests.results.map((r, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-3 text-sm">
              <div>
                <div className="font-medium">{r.name}</div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400">{r.detail}</div>
              </div>
              <Badge kind={r.status}>{r.status}</Badge>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Negotiation AI</h2>
          <button onClick={runNegotiation} disabled={negotiating} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
            {negotiating ? "Generating…" : "Generate negotiation email"}
          </button>
        </div>
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
      </section>
    </div>
  );
}
