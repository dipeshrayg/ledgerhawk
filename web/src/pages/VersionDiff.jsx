import { useParams } from "react-router-dom";
import { Badge } from "../components/Badge";
import { Breadcrumb } from "../components/Breadcrumb";
import { ErrorState, Loading } from "../components/States";
import { StatCard } from "../components/StatCard";
import { api, fmtMoney } from "../lib/api";
import { useApi } from "../lib/useApi";

const CHANGE_STYLE = {
  added: "border-emerald-300 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/30",
  removed: "border-red-300 bg-red-50 dark:border-red-900 dark:bg-red-950/30",
  modified: "border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30",
  new_risk: "border-red-300 bg-red-50 dark:border-red-900 dark:bg-red-950/30",
};

const CATEGORY_LABEL = {
  pricing: "Pricing", escalation: "Escalation", discount: "Discount",
  credit: "Credit", legal_risk: "Legal risk", other: "Other",
};

function ParamBlock({ params }) {
  if (params == null) return <span className="text-neutral-400 italic">absent</span>;
  if (typeof params !== "object") return <span className="mono">{String(params)}</span>;
  return (
    <span className="mono">
      {Object.entries(params).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(", ")}
    </span>
  );
}

export function VersionDiff() {
  const { pairId } = useParams();
  const { data, error, loading } = useApi(() => api.diff(pairId), [pairId]);

  if (loading) return <Loading label="Compiling both versions and diffing…" />;
  if (error) return <ErrorState message={error} />;

  const impact = parseFloat(data.dollar_impact_36mo);

  return (
    <div className="space-y-6">
      <div>
        <Breadcrumb trail={[{ label: "Dashboard", to: "/app" }, { label: "Version Diff" }]} />
        <h1 className="text-2xl font-bold">Version Diff - {data.vendor_name}</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">git diff for contracts: v1 vs. v2, compiled and compared rule-by-rule.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <StatCard label="v1 - 36mo projected" value={fmtMoney(data.total_v1_36mo)} />
        <StatCard label="v2 - 36mo projected" value={fmtMoney(data.total_v2_36mo)} />
        <StatCard label="Dollar impact" value={fmtMoney(data.dollar_impact_36mo)} tone={impact > 0 ? "bad" : "good"} />
      </div>

      <div className="flex flex-wrap gap-2">
        {data.categories.map((c) => (
          <Badge key={c} kind="neutral">{CATEGORY_LABEL[c] || c}</Badge>
        ))}
      </div>

      <div className="space-y-3">
        {data.changes.map((c, i) => (
          <div key={i} className={`rounded-lg border p-4 ${CHANGE_STYLE[c.change] || ""}`}>
            <div className="flex items-center justify-between">
              <span className="mono text-sm font-semibold">{c.rule_key}</span>
              <div className="flex gap-2">
                <Badge kind="neutral">{CATEGORY_LABEL[c.category] || c.category}</Badge>
                <Badge kind={c.change === "removed" ? "high" : c.change === "added" ? "low" : "medium"}>{c.change}</Badge>
              </div>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-4 text-xs">
              <div>
                <div className="mb-1 font-semibold text-red-700 dark:text-red-400">- v1</div>
                <ParamBlock params={c.v1} />
              </div>
              <div>
                <div className="mb-1 font-semibold text-emerald-700 dark:text-emerald-400">+ v2</div>
                <ParamBlock params={c.v2} />
              </div>
            </div>
            <p className="mt-2 text-sm">{c.explanation}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
