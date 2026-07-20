import { describe, expect, it } from "vitest";
import { answerStatic } from "./copilotStatic";

// Mirrors api/tests/test_copilot.py's fixture shape and the same 8
// scripted questions, so the JS port is checked against the same script
// as the Python original it's meant to stay in lockstep with.
const graph = {
  vendor_names: { megacloud: "MegaCloud Inc.", salesforge: "SalesForge CRM" },
  invoice_counts: { megacloud: 12, salesforge: 12, nimbuspay: 12, crestline: 12, peakservers: 12 },
  findings: [
    { vendor_id: "megacloud", invoice_id: "megacloud-202601", delta: "14326.00", rule_key: "pricing.escalation.default", clause_quote: "quote a", clause_source: "Amendment 2", explanation: "escalation miscalculated" },
    { vendor_id: "salesforge", invoice_id: "salesforge-202510", delta: "6600.00", rule_key: "pricing.per_unit.user", clause_quote: "quote b", clause_source: "MSA 6.2", explanation: "rate above contract" },
  ],
};

const QUESTIONS = [
  "Which vendors violated their contracts?",
  "Show overcharges above $5,000",
  "Which clauses caused the most loss?",
  "Why did megacloud's cost jump?",
  "What is our total recovered leakage?",
  "Which vendor has the highest risk?",
  "Show findings for salesforge",
  "What's our compliance rate?",
];

describe("copilotStatic.answerStatic", () => {
  it("answers all 8 scripted questions from graph data, never falling through", () => {
    for (const q of QUESTIONS) {
      const result = answerStatic(q, graph);
      expect(result.source, `question fell through: ${q}`).toBe("graph");
      expect(result.answer).toBeTruthy();
    }
  });

  it("total recovered sums only positive deltas", () => {
    const result = answerStatic("What is our total recovered leakage?", graph);
    expect(result.answer).toContain("20,926.00");
  });

  it("compliance rate matches invoice_counts and finding uniqueness", () => {
    const result = answerStatic("What's our compliance rate?", graph);
    expect(result.answer).toContain("58/60");
  });

  it("unmatched question returns source: none, not a guess", () => {
    const result = answerStatic("what's the weather like", graph);
    expect(result.source).toBe("none");
  });

  it("vendor matching is case-insensitive and matches by first name token", () => {
    const result = answerStatic("show findings for MegaCloud", graph);
    expect(result.answer).toContain("1 finding(s)");
  });
});
