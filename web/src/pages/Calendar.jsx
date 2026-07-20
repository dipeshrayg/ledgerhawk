import { Link } from "react-router-dom";
import { Badge, DaysBadge } from "../components/Badge";
import { Breadcrumb } from "../components/Breadcrumb";
import { Empty, ErrorState, Loading } from "../components/States";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";

const TYPE_LABEL = {
  renewal: "Renewal",
  renewal_notice_deadline: "Notice deadline",
  discount_expiry: "Discount expiry",
  credit_expiry: "Credit expiry",
  escalation_effective: "Escalation",
};

const TYPE_TONE = {
  renewal: "medium",
  renewal_notice_deadline: "high",
  discount_expiry: "high",
  credit_expiry: "high",
  escalation_effective: "medium",
};

export function Calendar() {
  const { data, error, loading } = useApi(api.calendar, []);
  if (loading) return <Loading label="Building renewal risk calendar…" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-4">
      <div>
        <Breadcrumb trail={[{ label: "Dashboard", to: "/app" }, { label: "Calendar" }]} />
        <h1 className="text-2xl font-bold">Renewal Risk Calendar</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">Every renewal, notice deadline, discount/credit expiry, and scheduled escalation across all vendors, as of {data.today}.</p>
      </div>

      {data.events.length === 0 ? (
        <Empty message="No upcoming calendar events." />
      ) : (
        <div className="space-y-2">
          {data.events.map((e, i) => (
            <div key={i} className="flex items-center justify-between rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
              <div className="flex items-center gap-3">
                <Badge kind={TYPE_TONE[e.type] || "neutral"}>{TYPE_LABEL[e.type] || e.type}</Badge>
                <div>
                  <Link to={`/app/vendors/${e.vendor_id}`} className="font-medium hover:underline">{e.vendor_name}</Link>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">{e.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-sm">
                {e.projected_cost_impact_pct != null && (
                  <span className="text-red-600 dark:text-red-400">+{e.projected_cost_impact_pct}%</span>
                )}
                <span className="text-neutral-500 dark:text-neutral-400">{e.date}</span>
                <DaysBadge days={e.days_remaining} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
