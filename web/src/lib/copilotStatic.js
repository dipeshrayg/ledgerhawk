// Client-side port of api/app/pipeline/copilot.py's intent matching, for
// the static (GitHub Pages) deployment where there's no backend to call.
// Same rules, same graph-sourced-only answers, operating on the exported
// graph.json (findings + vendor_names + invoice_counts) instead of a live
// DB query. Kept in lockstep with the Python version by hand -- if you
// change one, change the other.

const INTENT_PATTERNS = [
  ["vendors_violated", /which vendors?.*violat|who violated|vendors? .*(broke|breach)/i],
  ["overcharges_above", /overcharges?.*above|above \$?[\d,]+/i],
  ["top_clauses", /which clauses?|costliest clause|most loss|clause.*most/i],
  ["explain_jump", /why did|why.*jump|why.*cost|why.*increase|why.*spike/i],
  ["total_recovered", /total recovered|how much.*recover|total leakage/i],
  ["top_risk_vendor", /highest risk|riskiest|most findings|worst vendor/i],
  ["vendor_findings", /findings for|show me .*findings|discrepancies for/i],
  ["compliance_rate", /compliance rate|pass rate|percent passing|% passing/i],
];

function matchVendor(question, vendorNames) {
  const q = question.toLowerCase();
  for (const [vid, name] of Object.entries(vendorNames)) {
    if (q.includes(vid.toLowerCase()) || q.includes(name.toLowerCase()) || q.includes(name.split(" ")[0].toLowerCase())) {
      return vid;
    }
  }
  return null;
}

function extractAmount(question) {
  const m = question.match(/\$?([\d,]+(?:\.\d+)?)/);
  return m ? parseFloat(m[1].replace(/,/g, "")) : 5000;
}

function fmt(n) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function answerStatic(question, graph) {
  const { findings, vendor_names: vendorNames, invoice_counts: invoiceCounts } = graph;
  const q = question.toLowerCase();
  const intent = INTENT_PATTERNS.find(([, re]) => re.test(q))?.[0];

  const findingsForVendor = (vid) => findings.filter((f) => f.vendor_id === vid);
  const vendorsWithViolations = () => [...new Set(findings.map((f) => f.vendor_id))].sort();
  const totalRecovered = () =>
    findings.filter((f) => parseFloat(f.delta) > 0).reduce((s, f) => s + parseFloat(f.delta), 0);

  const topClauses = (n = 5) => {
    const byKey = {};
    const quotes = {};
    for (const f of findings) {
      const key = f.rule_key || f.clause_quote;
      byKey[key] = (byKey[key] || 0) + parseFloat(f.delta);
      quotes[key] = f.clause_quote;
    }
    return Object.entries(byKey)
      .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
      .slice(0, n)
      .map(([k, v]) => ({ rule_key: k, total_delta: v, clause_quote: quotes[k] }));
  };

  const vendorRiskRanking = () => {
    const byVendor = {};
    const counts = {};
    for (const f of findings) {
      byVendor[f.vendor_id] = (byVendor[f.vendor_id] || 0) + parseFloat(f.delta);
      counts[f.vendor_id] = (counts[f.vendor_id] || 0) + 1;
    }
    return Object.entries(byVendor)
      .sort((a, b) => b[1] - a[1])
      .map(([vid, delta]) => ({ vendor_id: vid, vendor_name: vendorNames[vid] || vid, total_delta: delta, finding_count: counts[vid] }));
  };

  if (intent === "vendors_violated") {
    const vendors = vendorsWithViolations();
    const names = vendors.map((v) => vendorNames[v] || v);
    return {
      answer: vendors.length ? `${vendors.length} vendor(s) have findings: ${names.join(", ")}.` : "No vendors have any findings.",
      source: "graph",
    };
  }

  if (intent === "overcharges_above") {
    const threshold = extractAmount(question);
    const found = findings.filter((f) => Math.abs(parseFloat(f.delta)) > threshold);
    const lines = found.map((f) => `${vendorNames[f.vendor_id] || f.vendor_id} / ${f.invoice_id}: ${fmt(parseFloat(f.delta))}`);
    return {
      answer: found.length ? `${found.length} finding(s) above ${fmt(threshold)}:\n${lines.join("\n")}` : `No findings above ${fmt(threshold)}.`,
      source: "graph",
    };
  }

  if (intent === "top_clauses") {
    const top = topClauses(5);
    const lines = top.map((c) => `${c.rule_key}: ${fmt(c.total_delta)} ("${c.clause_quote.slice(0, 80)}...")`);
    return { answer: top.length ? `Costliest clause patterns:\n${lines.join("\n")}` : "No clause-level losses found.", source: "graph" };
  }

  if (intent === "explain_jump") {
    const vid = matchVendor(question, vendorNames);
    if (!vid) return { answer: "Which vendor did you mean? Try naming one, e.g. 'Why did MegaCloud's cost jump?'", source: "graph" };
    const vf = findingsForVendor(vid);
    if (!vf.length) return { answer: `${vendorNames[vid] || vid} has no discrepancies on record.`, source: "graph" };
    const f = vf.reduce((a, b) => (Math.abs(parseFloat(b.delta)) > Math.abs(parseFloat(a.delta)) ? b : a));
    return {
      answer: `${f.explanation} Clause (${f.clause_source}): "${f.clause_quote}" Delta: ${fmt(parseFloat(f.delta))} on invoice ${f.invoice_id}.`,
      source: "graph",
    };
  }

  if (intent === "total_recovered") {
    return { answer: `Total recovered leakage across all vendors: ${fmt(totalRecovered())}.`, source: "graph" };
  }

  if (intent === "top_risk_vendor") {
    const ranking = vendorRiskRanking();
    if (!ranking.length) return { answer: "No vendors currently have findings.", source: "graph" };
    const top = ranking[0];
    return { answer: `${top.vendor_name} carries the most risk: ${fmt(top.total_delta)} across ${top.finding_count} finding(s).`, source: "graph" };
  }

  if (intent === "vendor_findings") {
    const vid = matchVendor(question, vendorNames);
    if (!vid) return { answer: "Which vendor did you mean?", source: "graph" };
    const vf = findingsForVendor(vid);
    const lines = vf.map((f) => `${f.invoice_id}: ${fmt(parseFloat(f.delta))} -- ${f.explanation}`);
    return {
      answer: vf.length ? `${vendorNames[vid] || vid} has ${vf.length} finding(s):\n${lines.join("\n")}` : `${vendorNames[vid] || vid} has zero findings -- clean record.`,
      source: "graph",
    };
  }

  if (intent === "compliance_rate") {
    const total = Object.values(invoiceCounts).reduce((a, b) => a + b, 0);
    const failing = new Set(findings.map((f) => `${f.vendor_id}:${f.invoice_id}`)).size;
    const passing = total - failing;
    const pct = total ? (passing / total) * 100 : 100;
    return { answer: `Compliance rate: ${pct.toFixed(1)}% (${passing}/${total} invoices passing).`, source: "graph" };
  }

  return {
    answer:
      "I couldn't match that to a known query. Try: vendors with violations, overcharges above $X, costliest clauses, " +
      "why a vendor's cost jumped, total recovered leakage, highest-risk vendor, findings for a vendor, or compliance rate.",
    source: "none",
  };
}
