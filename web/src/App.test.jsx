import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const DASHBOARD_FIXTURE = {
  demo_mode: true, llm_mode: "demo", total_recovered: "0.00", forecasted_12mo_leakage_delta: "0.00",
  compliance_pct: 100, total_invoices: 0, failing_invoices: 0, vendor_risk_ranking: [],
  top_violating_clauses: [], upcoming_renewals_90d: [], monthly_trend: [], vendor_count: 0,
};

beforeEach(() => {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ vendors: [], demo_mode: true, llm_mode: "demo", status: "ok", questions: [], ...DASHBOARD_FIXTURE }),
    })
  );
});

describe("App", () => {
  it("renders the marketing homepage at / without crashing", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    await waitFor(() => expect(container.textContent).toContain("LedgerHawk"));
    expect(container.textContent).toContain("Nobody's running the tests");
  });

  it("renders the CFO Dashboard at /app without crashing", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/app"]}>
        <App />
      </MemoryRouter>
    );
    await waitFor(() => expect(container.textContent).toContain("LedgerHawk"));
    expect(container.textContent).toContain("CFO Dashboard");
  });
});
