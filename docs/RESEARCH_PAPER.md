# LedgerHawk: Compiling Enterprise Contracts into Executable Pricing Rules for Automated Invoice Reconciliation

**Author:** Dipesh Ray, Ulster University
**Contact:** ray-d@ulster.ac.uk
**Repository:** [github.com/dipeshrayg/ledgerhawk](https://github.com/dipeshrayg/ledgerhawk)
**Date:** July 2026

## Abstract

Enterprise vendor contracts specify exact pricing terms - per-unit rates,
volume tiers, escalation caps, time-bound discounts - but almost nobody
re-derives the correct invoice amount from those terms before paying it.
The result is invisible billing leakage: a vendor's invoice looks entirely
normal even when it silently violates the contract. We present LedgerHawk,
a system that treats a contract as source code: it compiles pricing clauses
into a typed intermediate representation (a Contract AST), lowers that into
an executable rule set (a Pricing DSL), and replays every invoice against a
deterministic billing engine to compute the exact amount that should have
been charged. The central design constraint is that no language model ever
touches a dollar figure - LLMs translate contract text into structured
rules and draft prose around findings, but every arithmetic operation runs
through plain, unit-tested code. We built a synthetic benchmark of five
vendor contracts, 60 invoices, and 14 deliberately planted billing errors -
covering seat drift, double-billed one-time fees, unprorated mid-cycle
upgrades, miscalculated escalation, dropped discounts, and a multi-document
precedence conflict between an MSA, three amendments, and an executed email
agreement. LedgerHawk recovers all 14 planted errors ($86,420.40 total)
with zero false positives across the 46 clean invoices, reconciles the full
set in under 7 milliseconds, and resolves the multi-document precedence
case correctly, including provenance back to the specific clause. We
discuss the architecture, the evaluation methodology, and the limits of a
synthetic benchmark built by the same person who built the detector.

## 1. Introduction

A vendor contract is, functionally, a pricing program. It takes usage as
input - seats, API calls, storage - and a set of conditional rules -
tiers, caps, discount windows - and produces a dollar amount as output.
Nobody treats it that way. Contracts sit in a document management system
as PDFs; invoices arrive by email; someone in accounts payable checks that
the total looks roughly right and approves it. The pricing logic itself is
never executed against the usage data independently. It's read once, by a
human, at signing time, and then trusted indefinitely.

That trust is misplaced in a specific, measurable way. Vendor billing
systems apply escalations on the wrong date, forget that a loyalty
discount was extended by a follow-up email, bill a seat count from before
a downgrade, or double-post a one-time fee. None of these show up as
anomalies. They show up as ordinary-looking line items on an ordinary-
looking invoice. The only way to catch them is to independently recompute
the correct charge from the contract's actual terms and compare - which is
exactly the work nobody has time to do by hand, every month, for every
vendor.

This paper describes LedgerHawk, a system built around one constraint:
**the money math has to be independently, deterministically verifiable, or
none of this is worth building.** An LLM that reads a contract and writes
a plausible-sounding dollar figure is not an improvement over the status
quo - it just moves the trust problem from "trust the vendor's billing
system" to "trust the model's arithmetic," and large language models are
measurably unreliable at exactly this kind of multi-step numerical
reasoning (see Section 2). LedgerHawk instead draws a hard boundary: LLMs
are permitted to translate language into structure (contract clauses into
typed rules, findings into prose), and a separate, deterministic,
unit-tested engine is the only thing permitted to multiply a rate by a
quantity.

Our contribution is threefold: (1) a compiler-pipeline architecture -
Contract AST, Pricing DSL, precedence resolver, deterministic billing
engine, evidence generator - that keeps the LLM/arithmetic boundary
enforced at the type level, not just by convention; (2) a synthetic
benchmark methodology for evaluating this class of system, built by
generating ground-truth expected invoices from the compiled rules and then
mutating specific line items to plant known, labeled discrepancies; and
(3) an open, runnable reference implementation with a live static
deployment, so the claims in this paper can be checked directly rather
than taken on faith.

## 2. Related Work

**Contract understanding as NLP.** CUAD (Hendrycks, Burns, Chen, and Ball,
*CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*, NeurIPS
2021, arXiv:2103.06268) established a benchmark of over 500 contracts and
13,000 expert clause annotations across 41 categories, and showed that even
strong transformer models leave substantial room for improvement at
locating the right clause. That line of work treats contract understanding
as an extraction and retrieval problem: find the clause, highlight it for
a human. LedgerHawk sits one layer downstream of that - it assumes clause
extraction is achievable (and, in demo mode, sidesteps live extraction
entirely by shipping pre-verified fixtures) and focuses on what happens
*after* extraction, when a clause has to become an executable rule that
produces a number.

**LLM reliability on numerical reasoning.** Recent work on LLM hallucination
in financial contexts is directly relevant to why we drew the boundary
where we did. *FAITH: A Framework for Assessing Intrinsic Tabular
Hallucinations in Finance* (arXiv:2508.05201, 2025) found that leading
models collapse from 95.6% accuracy on simple lookups to near zero on
multivariate calculations over financial tables - the exact shape of task
a contract's escalation-and-discount stack requires. *Neuro-Symbolic
Financial Reasoning via Deterministic Fact Ledgers and Adversarial
Low-Latency Hallucination Detector* (arXiv:2603.04663, 2026) argues for the
same architectural response we independently arrived at: pair a language
model with a deterministic, symbolic ledger rather than asking the model to
hold the arithmetic itself. LedgerHawk can be read as an instance of that
pattern, applied specifically to contract-versus-invoice reconciliation.

**Business rules engines.** Compiling business logic into an executable,
declarative rule set - rather than hand-coding it - is an established
pattern outside the contracts domain; rules engines such as Drools pair a
domain-specific language with a deterministic evaluation engine so business
logic can be authored close to plain language while still executing
predictably. LedgerHawk's Pricing DSL follows the same shape: JSON rules
with no `eval`, interpreted by a fixed, auditable engine. The novelty here
isn't the rules-engine pattern itself; it's applying that discipline to a
domain - contract pricing - where the rules currently get authored by
whichever LLM extraction pipeline happens to run, with no independent
execution layer checking the output.

## 3. System Architecture

The pipeline has eight stages, each with a typed Pydantic artifact as its
output, so no stage can silently pass an untyped dict to the next:

```
Document → Extraction → Clause Segmentation → Contract Agent (LLM)
  → Contract AST → Pricing Agent (LLM) → Pricing DSL → Static Validator
  → Precedence Resolver → Billing Engine (deterministic) → Reconciliation
  → Violation Graph → Evidence Generator
```

### 3.1 Contract AST

The Contract AST models parties, term (start/end, renewal type, notice
window), and a list of pricing clauses. Every clause and every term carries
a `Provenance` record: the source document, section number, and a verbatim
quote. The system will not synthesize a finding without a quote - the
Evidence Generator falls back to an explicit "no contractual basis found"
label rather than inventing a citation.

### 3.2 Pricing DSL

The AST is lowered into a Pricing DSL: flat fees, per-unit rates, graduated
volume tiers, time-bound discounts, escalation clauses (percentage, cadence,
cumulative cap), one-time charges, and rollover credits. All monetary
values are serialized as strings and parsed to `Decimal` at the engine
boundary - floating-point arithmetic is never used for money, which matters
over a 36-month forecast where float drift would compound.

### 3.3 Precedence resolution

A single vendor's terms often come from more than one document - an MSA, a
sequence of amendments, and occasionally an executed email. Each rule
carries a `rule_key` (grouping clauses that govern the same economic fact,
e.g. `pricing.per_unit.seat`) and each document carries an `effective_date`,
an `executed` flag, and an `authority_rank`. Resolving the effective term
for a given date is a three-step filter: only executed documents can win;
among active candidates, the latest `effective_from` wins; ties break on
`authority_rank`. This is the mechanism that lets an email extending a
discount correctly override a superseded amendment - Section 5.3 reports
the result on our benchmark's precedence case.

One implementation lesson surfaced during development is worth recording
because it is easy to get subtly wrong: precedence's `executed` filter is
*correct* for reconciliation (an unsigned draft must never govern what a
customer actually owes) and *incorrect* for forecasting or pre-sign review,
which are inherently hypothetical ("what would this cost if the current
trajectory continues" or "what would this cost if I sign this proposal").
The same resolver function serves both callers; the fix was an explicit
`documents=None` bypass for the hypothetical callers, not a second
resolver. Two real bugs in early development - a forecast that always
returned zero for a not-yet-signed proposal, and a contract test that
passed vacuously (0 == 0) for the same reason - both traced to this single
conflation, and both were caught by writing a test that asserted a
non-trivial result rather than merely asserting "no exception."

### 3.4 Deterministic billing engine

The billing engine is plain Python: given a set of already-resolved rules
and a period's usage, it computes per-unit charges (with optional daily
proration for mid-period changes, verified correct across a leap-year
February), graduated tier charges, escalation-adjusted rates, one-time
charges gated by date, and discount/credit adjustments, then rounds every
line to the cent with `ROUND_HALF_UP` before summing - matching how a real
invoice presents line items rather than summing raw fractional values and
rounding once at the end. It contains no LLM call, no network call, and no
source of nondeterminism. Its behavior is specified entirely by 9
unit tests covering tiered pricing, leap-year proration, escalation caps,
and credit rollover, independent of any seeded demo data.

### 3.5 Evidence generation and the violation graph

Reconciliation diffs an expected invoice against an actual one by matching
line items on description text (as a multiset, so a duplicated line or a
missing credit both surface correctly), then emits one `Finding` per
failing invoice: the responsible rule, its verbatim clause quote, a
line-by-line math trace, the dollar delta, and a confidence score (1.0 when
a specific rule is implicated, 0.75 for an unattributed charge with no
contractual basis at all). A thin `ViolationGraph` class indexes findings
by vendor, invoice, and clause for querying - at this benchmark's scale (5
vendors, 60 invoices), an in-memory index over a list of findings is a
more honest engineering choice than standing up a graph database for the
sake of the word "graph."

### 3.6 The LLM/determinism boundary

Six components are described as "agents" with typed input/output
contracts: a Contract Agent and Pricing Agent (LLM, used for live
extraction; retried on schema-validation failure), a Billing Agent (never
an LLM - it *is* the billing engine described above), a Risk Agent
(deterministic lint rules, with an optional LLM-written summary sentence
layered on top), a Negotiation Agent (computes a real savings figure by
diffing two forecast replays, then optionally asks an LLM to draft the
covering email), and a Report Agent (drafts a dispute letter whose every
fact - quote, rule, math, delta - is copied from an already-computed
`Finding`, never generated). Every one of these has a deterministic
fallback that runs with no API key configured; this is what lets the
system run identically in "demo fixtures" mode and "live LLM" mode, and
it's why the entire evaluation in Section 5 required zero calls to any
language model.

## 4. Evaluation Methodology

### 4.1 Benchmark construction

We built five vendor contracts - one large multi-document flagship
(MegaCloud: an MSA, three amendments, and an executed email agreement) and
four single-document vendors spanning CRM, payroll, office supplies, and
cloud hosting - each with 12 months of invoices. Ground truth was generated
by running the actual billing engine and precedence resolver against each
period's usage to compute the contractually correct invoice, then
deliberately mutating 14 specific invoices (one to six per vendor) with a
labeled, code-level transformation: inflate a quantity, duplicate a line
item, drop a discount or credit line, or substitute a miscalculated rate.
The remaining 46 invoices were left untouched, so they equal the engine's
own output exactly by construction - these are the negative class the
system must not flag.

This generate-then-mutate methodology has one structural advantage over
hand-authoring both the expected and actual figures separately: it removes
arithmetic transcription error from the benchmark itself. Every "expected"
number is the engine's real output, not a number a human computed
separately and might have gotten wrong. One vendor (PeakServers Hosting)
was left with zero mutations, specifically to test whether the system
flags a well-behaved vendor's invoices - a common failure mode for
threshold-based anomaly detectors that don't have a genuine ground truth
to compare against.

### 4.2 Metrics

We report recall (planted errors detected / planted errors total),
precision (correctly-flagged invoices / all-flagged invoices, equivalently
1 − false-positive rate on the clean set), dollar accuracy (computed delta
against the documented, engine-derived ground truth), and wall-clock
latency for reconciling the full benchmark.

## 5. Results

### 5.1 Detection accuracy

| Metric | Result |
|---|---|
| Planted errors | 14 |
| Errors detected | 14 (100% recall) |
| Clean invoices | 46 |
| False positives | 0 (100% precision) |
| Total recovered leakage | $86,420.40 |
| Vendors with zero findings | 1 of 5 (PeakServers Hosting, 12/12 clean) |

Table 1 breaks this down by vendor and error class.

| Vendor | Findings | Recovered | Error classes present |
|---|---:|---:|---|
| MegaCloud Inc. | 6 | $75,885.90 | seat drift, double-billed fee, unprorated upgrade, miscalculated escalation, dropped credit, dropped discount |
| SalesForge CRM | 3 | $8,274.00 | above-contract rate, early escalation, tier miscalculation |
| NimbusPay | 3 | $1,802.50 | quantity drift, double-billed fee, flat-fee creep |
| Crestline Office Supplies | 2 | $458.00 | quantity drift, flat-fee overcharge |
| PeakServers Hosting | 0 | $0.00 | none (control) |

### 5.2 Precedence resolution

The MegaCloud benchmark case has five governing documents: an MSA
(2022), Amendment 1 (2024, a discount later superseded), Amendment 2
(2025, revised rate and escalation), Amendment 3 (2025, a service credit),
and an email agreement executed in November 2025 extending the original
loyalty discount through the following year. Querying effective terms as
of any date within the extended window correctly returns the email's
discount rule rather than the expired amendment's, with `source_name`
provenance reading "Email Agreement (2025-11-15)" - confirmed by a
dedicated test and reproducible directly against the live system's Rule
Inspector view.

### 5.3 Forecast replay

Deterministically replaying MegaCloud's compiled contract 36 months
forward (holding usage at its last known baseline) surfaces a $67,494.40
per-month cost jump five months out, coinciding exactly with the
contract's 2027 renewal, where a 15% auto-renewal uplift compounds with
already-scheduled escalation in the same billing period - an $809,932.80
annualized impact, computed, not estimated.

### 5.4 Performance

Reconciling all 60 invoices across all 5 vendors - including precedence
resolution and evidence generation for every invoice - completes in 6.45
milliseconds (0.107ms per invoice) on ordinary developer hardware, no
caching. This is unsurprising: the entire computation is arithmetic over a
few dozen typed objects, with no network call and no model inference in
the loop. It is nonetheless the number that matters most for a system
whose value proposition is "run this on every invoice, every time" - an
architecture that required a model call per invoice would not be able to
make that claim at this cost or latency.

### 5.5 Test coverage

The reference implementation carries 64 automated tests: 9 on the billing
engine alone (graduated tiers, leap-year proration, escalation caps,
credit rollover), 5 on the static validator, 6 on precedence resolution, 4
on forecast replay, 2 on the diff engine, 4 on the violation graph, 4 on
the contract-test runner, 4 on connector behavior, 4 on the individual
agents, 3 on the audit copilot's scripted query patterns, 14 API-level
integration tests, and a 7-test end-to-end suite that asserts the exact
figures in Section 5.1 against the live reconciliation pipeline, not a
mock. The full suite runs in under 5 seconds.

## 6. Discussion

### 6.1 Why determinism, specifically, is the load-bearing decision

The result most worth foregrounding is not the 100% recall - a benchmark
built by the same person who built the detector should be expected to
score well on its own benchmark, and Section 6.3 addresses that directly.
The more interesting result is that the number *is* 100%, not "97%,
occasionally off by a rounding error the model introduced." A
probabilistic system evaluated on this same benchmark could plausibly
match its recall while still being wrong about the dollar amount on any
individual finding, because the arithmetic itself would be a model output.
Every dollar figure LedgerHawk reports is a `Decimal` computed by a
function with unit tests that don't reference the demo data at all - the
$86,420.40 figure is not a metric the system reports about itself so much
as an arithmetic fact that follows mechanically from 14 specific,
inspectable code-level mutations.

### 6.2 Limitations

The benchmark is synthetic. Real vendor contracts are messier than the
five constructed here: ambiguous clause language, contradictory
amendments with no clean precedence signal, units of measure that don't
map cleanly onto "seats" or "GB," and OCR noise in scanned PDFs that this
implementation's extraction path has not been evaluated against at all -
the live-LLM extraction agents are unit-tested for schema conformance and
retry behavior, but no real, arbitrary uploaded contract has been run
through them end-to-end in this work. The billing engine's escalation
model compounds on a fixed annual anniversary clock regardless of a rule's
stated cadence; a quarterly-escalation clause is flagged by the validator
as elevated risk but not given distinct quarterly-compounding arithmetic -
a deliberate scope cut, documented in the repository, not a silent gap.
Benchmarks in this dataset also assume a single implicit currency per
vendor; multi-currency and FX-aware reconciliation is unimplemented.

### 6.3 Threats to validity

The most direct threat to this evaluation's validity is that the same
person designed the benchmark's 14 discrepancies and the detection logic
that catches them. We mitigated this in one specific way: the evidence
generator's matching logic is generic (it diffs line-item descriptions as
a multiset with no per-error-type special case), so it cannot have been
tuned to any individual planted pattern - it was written before the final
mutation set was finalized and never modified afterward to accommodate a
specific case. That is a partial mitigation, not a resolution. A stronger
test would come from an independent party constructing a hidden benchmark,
or - better - from real vendor contract and invoice data, which was
unavailable for this work for the ordinary reason that most vendor billing
data is confidential.

### 6.4 What would need to change for real deployment

Three things stand between this implementation and a production
deployment: real ERP connectors (QuickBooks, NetSuite, SAP - the
Connector SDK's `InvoiceSource` interface is built to accept these; a
MockERP simulator and a CSV drop-folder watcher are the reference
implementations today), validated live-document extraction against real,
messy contract PDFs rather than pre-verified fixtures, and multi-tenant
data isolation, since the current implementation assumes a single
customer's data in a single SQLite file.

## 7. Conclusion

Contract-versus-invoice reconciliation is a task where the arithmetic
matters more than the language model, and most systems in this space get
that ordering backward - reaching for a general-purpose LLM to produce a
dollar figure directly from unstructured text. LedgerHawk compiles the
contract once, into a typed, executable rule set, and puts a deterministic
engine - not a model - in charge of every calculation downstream. On a
synthetic but code-verified benchmark of 60 invoices and 14 planted
errors, that architecture recovers every planted error, produces zero
false positives, resolves a genuine multi-document precedence conflict
correctly, and does the full computation in under 7 milliseconds. The
reference implementation, the benchmark generator, and a live, publicly
runnable deployment are released under the MIT license at
github.com/dipeshrayg/ledgerhawk, so every claim in this paper can be
checked directly against the code that produced it.

## Acknowledgments

This work was conducted independently by its author and is not affiliated
with, endorsed by, or representative of any real company; all vendor
names and contract terms in the benchmark dataset are fictional. No
external funding was received for this work.

## References

1. Hendrycks, D., Burns, C., Chen, A., & Ball, S. (2021). *CUAD: An
   Expert-Annotated NLP Dataset for Legal Contract Review*. NeurIPS 2021.
   arXiv:2103.06268.
2. *FAITH: A Framework for Assessing Intrinsic Tabular Hallucinations in
   Finance.* arXiv:2508.05201 (2025).
3. *Neuro-Symbolic Financial Reasoning via Deterministic Fact Ledgers and
   Adversarial Low-Latency Hallucination Detector.* arXiv:2603.04663
   (2026).
4. *Business rules engine.* Wikipedia, retrieved July 2026 - general
   background on domain-specific-language-driven rule evaluation
   (e.g. Drools), cited for the established rules-engine pattern this
   work adapts to the contracts domain.
