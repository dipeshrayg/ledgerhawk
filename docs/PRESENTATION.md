# LedgerHawk - Presentation Deck

14 slides, speaker notes included. Framing throughout: **"CI/CD for
Enterprise Contracts."**

---

## Slide 1 - Title

**LedgerHawk**
*CI/CD for Enterprise Contracts.*

Contracts are compiled into executable pricing rules. Invoices are test
runs. Overcharges are failing tests.

**Speaker notes:** Open with the tagline, then pause. The whole pitch is
in that one sentence - everything after this slide is proving it's true
and it's built, not just a slogan.

---

## Slide 2 - The problem: the invisible invoice leak

- Every enterprise contract has precise pricing terms: per-seat rates,
  escalation caps, time-bound discounts, proration rules.
- Every month, someone in AP pays the invoice. Nobody re-derives the
  correct number from the MSA + 3 amendments + that one email from 2025.
- The leakage looks *exactly like a normal invoice.* There's no anomaly to
  detect - the number is just wrong, quietly, forever.

**Speaker notes:** This isn't fraud, it's arithmetic drift at scale. Vendor
billing systems make mistakes, escalations get miscalculated, discounts
"expire" a year after they were extended by email. Multiply by hundreds of
vendor contracts and it's real money nobody is watching.

---

## Slide 3 - Why this is still unsolved

- Spend-management tools (Coupa, Ramp, Ironclad's contract search) surface
  *documents*, not *executable pricing logic.*
- Manual audits don't scale past a handful of vendors and don't survive an
  amendment chain.
- "Throw it at an LLM" produces a plausible-sounding number that is
  occasionally, invisibly, wrong - the worst possible failure mode for
  money math.

**Speaker notes:** The market has search and storage. It doesn't have
compilation and execution. That gap is the opportunity.

---

## Slide 4 - The insight: contracts-as-code

A contract *is* a program: inputs (usage), branches (tiers, discounts,
escalation triggers), and an output (a dollar amount). If you compile it
into that form once, you can:

- **Run** it against real invoices (reconciliation)
- **Replay** it forward in time (forecasting)
- **Diff** it against another version (negotiation prep)
- **Test** it the way you test code (contract unit tests)
- **CI** it the way you gate a merge (Contract CI)

**Speaker notes:** Once you see a contract as source code, the entire rest
of the product is "what do we already do with source code?" - that's not
a metaphor, it's the actual architecture.

---

## Slide 5 - Live demo

Walk through, live:

1. **CFO Dashboard** - $86,420.40 recovered, 76.7% compliance, vendor risk
   ranking.
2. **MegaCloud vendor detail → CI History** - click a FAIL, show the
   generated dispute letter with the verbatim clause quote and math trace.
3. **Rule Inspector** - the email agreement's discount, correctly
   overriding the superseded amendment, with provenance.
4. **Forecast tab** - the 36-month chart, the renewal-uplift jump.
5. **Version Diff** - DataVault v1→v2, red/green rule cards.
6. **Pre-Sign Review** - TalentBridge's failing contract test.
7. **Copilot drawer** - ask "Why did MegaCloud's cost jump?" live.

**Speaker notes:** This is the slide that's actually a browser tab. Follow
`docs/DEMO_DATA.md` for the exact numbers if asked to justify any figure on
screen.

---

## Slide 6 - The compiler pipeline

Document → Extraction → Segmentation → **Contract Agent (LLM)** →
**Contract AST** → **Pricing Agent (LLM)** → **Pricing DSL** → Static
Validator → Precedence Resolver → **Virtual Billing Engine** → Violation
Graph → Evidence Generator → API/Dashboards.

**Speaker notes:** Point at the typed arrow between every stage. Nothing
passes as a raw dict. That's what makes each stage independently testable
 - see the pytest suite, 64 tests, all green, most of them exercising these
exact modules with hand-built fixtures, not the demo data.

---

## Slide 7 - Multi-agent architecture (AI can't hallucinate money)

Six agents, typed contracts:

| Agent | LLM? |
|---|---|
| Contract Agent | Yes |
| Pricing Agent | Yes (schema-validated, retried) |
| **Billing Agent** | **Never. Plain Python, `Decimal`, unit-tested.** |
| Risk Agent | Optional (annotation prose only) |
| Negotiation Agent | Optional (email prose only) |
| Report Agent | Optional (prose only) |

**Speaker notes:** This is the slide to slow down on. The Billing Agent -
the one thing that ever multiplies a rate by a quantity - has no LLM
anywhere near it. Every other agent's LLM usage is *strictly cosmetic*: it
can make the email nicer or the executive summary read better, but every
dollar figure in this product is already computed before the LLM is ever
called, by code you can read in `billing_engine.py` in about five minutes.

---

## Slide 8 - Contract unit tests & CI

```yaml
- name: "Escalation cap must never exceed 10%"
  type: invariant
  rule_key: "pricing.escalation.default"
  field: cap_pct
  operator: "<="
  value: "10"
```

- Legal/procurement teams write assertions in YAML, same discipline as
  engineers writing unit tests.
- Every new invoice - upload or connector - auto-runs reconciliation +
  contract tests → PASS/FAIL, logged per vendor, badged like a CI build.
- `examples/github-actions-contract-ci.yml` - this runs in an actual repo,
  today, against the invoice fixtures checked into this repo.

**Speaker notes:** The TalentBridge proposal has a *deliberately* failing
test - its escalation clause is quarterly, contract standard is annual.
That's not a bug we're hiding, it's the feature working.

---

## Slide 9 - Forecasting as replay, not prediction

- No ML. The forecast is the same compiled DSL, walked forward 36 months,
  holding usage at today's baseline.
- Every scheduled event - an escalation anniversary, a discount expiry, an
  auto-renewal uplift - fires exactly when the contract says it will.
- MegaCloud: **$67,494.40/mo** jump five months out, **$809,932.80/yr**
  projected impact, at the exact month its 15% renewal uplift compounds
  with ongoing escalation.

**Speaker notes:** "Provable, not predicted" is the line. You can hand a
CFO this chart and the answer to "how do you know" is "read the contract,"
not "trust the model."

---

## Slide 10 - Evaluation

- **14/14 planted discrepancies recovered**, across 5 vendors, 60 invoices.
- **$86,420.40** total recovered leakage, **0 false positives** on the
  other 46 clean invoices.
- PeakServers Hosting: 12/12 clean invoices, 0 findings - the tool
  correctly does *not* cry wolf on a well-behaved vendor.
- MegaCloud precedence case resolves correctly: the executed email's
  discount extension is honored over the superseded amendment, with
  provenance shown.

**Speaker notes:** `api/tests/test_e2e.py` is this slide, executable. Run
it live if there's time: `pytest tests/test_e2e.py -v`.

---

## Slide 11 - Business impact

- $86k recovered on a 5-vendor demo portfolio. Real enterprises run
  hundreds of vendor contracts - the leakage scales roughly linearly with
  contract count and superlinearly with contract complexity (more
  amendments, more precedence edge cases, more opportunities for a vendor's
  billing system to drift from the signed terms).
- Forecast turns "we got overcharged" into "we know exactly when the next
  overcharge-shaped cost increase happens, months before it hits an
  invoice" - that's a renewal-negotiation lever, not just an audit finding.

**Speaker notes:** Frame ROI as "the product pays for itself off the first
vendor's first bad escalation," not as an aggregate abstract percentage.

---

## Slide 12 - Competitive landscape (honest)

- Spend-management and contract-lifecycle tools (Coupa, Ironclad, Sirion)
  do document storage, search, and workflow - genuinely useful, not what
  this replaces.
- LedgerHawk's claim is narrower and, we think, more defensible: **nobody
  else compiles a contract into an executable pricing engine with CI.**
- The closest adjacent category is invoice-audit consultancies -
  human-driven, non-scalable, and they don't leave you a reusable,
  versioned, testable artifact (the DSL) after the engagement ends.

**Speaker notes:** Don't oversell - this is a narrow, deep wedge, not a
full spend-management replacement. That's the honest and the more credible
pitch.

---

## Slide 13 - Roadmap

- **Real ERP connectors**: QuickBooks, NetSuite, SAP (the Connector SDK's
  `InvoiceSource` interface is built for this; MockERP and the CSV watcher
  are the reference implementations today).
- **Multi-currency**: the DSL's `Decimal` amounts are currency-agnostic
  today but assume a single implicit currency per vendor; FX-aware
  reconciliation is a natural extension.
- **Clause benchmark network**: today's benchmarks are illustrative and
  hand-set (`data/benchmarks.json`); a real product would crowdsource
  anonymized clause terms across customers for genuine market
  comparisons.
- **Live document upload → extraction UI**: the Contract/Pricing Agents'
  live-LLM extraction path is implemented and unit-tested but not yet
  wired into an upload flow in the frontend.

**Speaker notes:** Each roadmap item maps to a specific, named module
that's already scaffolded - this isn't a wish list, it's "here's exactly
where the next 3 sprints plug in."

---

## Slide 14 - Close

**LedgerHawk - CI/CD for Enterprise Contracts.**

Contracts compiled into executable pricing rules. Invoices are test runs.
Overcharges are failing tests - with evidence, dollar amounts, and a
dispute letter.

`./run.sh` - 3 commands, zero API keys, full dashboard.

**Speaker notes:** End on the quickstart, because it's true and it's the
best possible mic drop: everything in this deck is running on the laptop
in front of you right now.
