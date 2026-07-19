# Architecture

## Pipeline stages and artifacts

Each stage below is a separate, independently-testable module. The arrow is
a typed Pydantic artifact - nothing passes between stages as an untyped
dict.

| Stage | Module | Input → Output |
|---|---|---|
| Extraction | (pdfplumber, planned live path) | PDF/text → raw text |
| Clause Segmentation | (planned live path) | raw text → sectioned clauses |
| Contract Agent | `app/agents/compiler_agents.py::extract_contract_ast` | raw text → `ContractAST` |
| Pricing Agent | `app/agents/compiler_agents.py::lower_to_dsl` | `ContractAST` clauses → `PricingDSL` |
| Static Validator | `app/pipeline/validator.py` | `ContractAST` + `PricingDSL` → `list[LintFinding]` |
| Precedence Resolver | `app/pipeline/precedence.py` | `PricingDSL` + as-of date → winning `Rule` per `rule_key` |
| Billing Engine | `app/pipeline/billing_engine.py` | resolved rules + `UsagePeriod` → `ExpectedInvoice` (**deterministic, no LLM**) |
| Reconciliation | `app/pipeline/reconciliation.py` | `ExpectedInvoice` + `Invoice` → `ReconciliationResult` |
| Evidence Generator | `app/pipeline/evidence.py` | line-item diff → `Finding` (clause quote + math trace + delta + confidence) |
| Violation Graph | `app/pipeline/violation_graph.py` | `list[Finding]` → queryable index (vendor/clause/threshold queries) |
| Forecast | `app/pipeline/forecast.py` | `PricingDSL` + baseline usage → 36-month `ExpectedInvoice` series |
| Diff Engine | `app/pipeline/diff_engine.py` | two compiled contracts → categorized rule changes + $ impact |
| Contract Test Runner | `app/pipeline/contract_tests_runner.py` | `contract_tests.yaml` + `PricingDSL` → PASS/FAIL report |
| Copilot | `app/pipeline/copilot.py` | NL question + Violation Graph → graph-sourced answer |

Every one of these (except the two live-LLM-only Contract/Pricing Agent
paths, which demo vendors never call) has direct pytest coverage in
`api/tests/`.

## Why this decomposition

The instinct with an "AI contracts" product is to throw a document and a
question at an LLM and let it produce a dollar figure. LedgerHawk
deliberately refuses that shape. Splitting extraction (language → structure)
from execution (structure → arithmetic) means:

1. **The arithmetic is auditable independent of the LLM.** A billing engine
   bug is a `pytest` failure with a stack trace, not a hallucination you
   have to prompt your way out of.
2. **Demo mode isn't a fallback path bolted on afterward - it's the only
   path that matters for money.** Since the AST/DSL for every seeded vendor
   ships as a checked-in fixture (`api/data/fixtures/`), the entire
   Execute half of the pipeline runs with *zero* dependency on any LLM ever
   being called, in production or in this demo.
3. **Every number traces backward.** A `Finding` carries a `clause_quote`
   and `rule_id` - you can always ask "where did this dollar figure come
   from" and get a verbatim answer, not a paraphrase.

## Multi-document precedence

A vendor's rule set may span an MSA, several amendments, and an executed
email. `precedence.py` resolves, per `rule_key` and as-of date, the single
winning `Rule`:

1. Only `executed=True` documents can win (an unsigned draft never governs
   a real invoice) - see `resolve_effective_terms`.
2. Among active candidates (`effective_from <= as_of <= effective_to`), the
   one with the latest `effective_from` wins.
3. Ties are broken by `authority_rank` (sender-supplied ranking, e.g. an
   executed email outranking a same-dated internal memo).

Forecast (F2) and the contract test runner deliberately **do not** filter
by `executed` - they intentionally ask "what would this cost if signed /
if this trajectory continues," which is a different question from
reconciliation's "what does the signed contract actually require right
now." See the issue tracker for the two real bugs this distinction caused
during development - the same `effective_rules_dict` function is correct
for one caller and silently wrong for the other if you don't pass
`documents=None` deliberately.

## Multi-agent layer

| Agent | File | LLM? | Typed contract |
|---|---|---|---|
| Contract Agent | `agents/compiler_agents.py` | Yes (retried on schema failure) | raw text → `ContractAST` |
| Pricing Agent | `agents/compiler_agents.py` | Yes (retried on schema failure) | `ContractAST` clauses → `PricingDSL` |
| Billing Agent | `pipeline/billing_engine.py` + `pipeline/reconciliation.py` | **Never** | `PricingDSL` + usage → `ExpectedInvoice` |
| Risk Agent | `agents/risk_agent.py` | Optional (annotation only; findings are deterministic) | AST+DSL → risk findings + score |
| Negotiation Agent | `agents/negotiation_agent.py` | Optional (email prose only; savings figure is deterministic) | findings + benchmarks → terms + email + savings |
| Report Agent | `agents/report_agent.py` | Optional (prose only; every fact is copied from a `Finding`) | Violation Graph → executive summary + dispute letters |

`app/agents/llm_provider.py` is the single seam: `call_llm(prompt, system)`
returns `None` on missing key, network failure, or malformed response, and
every caller above has a deterministic template fallback. This is what
zero-key demo mode actually is - not a special case, just the path every
agent already has to support.

## Scaling

The demo runs on SQLite and a single process because the dataset is five
vendors and sixty invoices - anything heavier would be solving a problem
that doesn't exist yet. The path past that ceiling is deliberate, not an
afterthought, and part of it is already code rather than a slide:

- **Database.** `app/db.py` reads `DATABASE_URL` and only falls back to the
  bundled SQLite file if it's unset. Every query in the codebase goes
  through SQLAlchemy's engine/session - nothing touches `sqlite3` directly
  - so pointing `DATABASE_URL` at Postgres is a one-line config change, not
  a rewrite. When the URL isn't SQLite, the engine picks up a real
  connection pool (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`)
  instead of SQLite's single-file-handle model; `tests/test_db_config.py`
  pins that branching behavior so it can't silently regress.
- **API tier.** FastAPI holds no in-process state between requests (the
  one exception, the MockERP connector's poll cursor, is explicitly a demo
  convenience - see `app/routers/connectors.py`). That makes the API
  horizontally scalable as-is: run N replicas behind a load balancer, all
  pointed at the same Postgres instance, no sticky sessions required.
- **Read-heavy endpoints.** The dashboard and violation-graph queries
  recompute reconciliation from stored invoices on every request, which is
  cheap at demo scale (sub-10ms for 60 invoices, per the pytest timing) but
  is exactly the kind of thing a cache invalidated by "new invoice
  ingested" would flatten at real scale - Redis, keyed by vendor, sitting
  in front of `reconcile_all`.
- **Contract extraction at scale.** Today's Contract/Pricing Agents run
  synchronously inside the request. Real ingestion volume (hundreds of
  contracts uploaded at once) wants a background worker queue (Celery or
  RQ against the same Postgres or a Redis broker) so extraction doesn't
  block the request thread, with the client polling or getting a webhook
  when compilation finishes.
- **Multi-tenancy.** Every table in `app/models_db.py` would take an
  `org_id` column and every query a matching filter - the schema is
  already narrow enough (JSON-blob AST/DSL, not hundreds of normalized
  clause tables) that this is additive, not a redesign.

None of this is implemented beyond the database layer, on purpose - the
demo is sized for 5 vendors, not 50,000, and building the rest out now
would be solving a problem that doesn't exist yet. The point is that every
item above is an addition to the current architecture, not a rewrite of
it: nothing here requires undoing a decision already made.

## Design tradeoffs

- **SQLite + JSON-blob storage for AST/DSL** (`app/models_db.py`): the AST
  and DSL are already validated, typed Pydantic documents. Normalizing
  every clause and rule into relational columns would add joins without
  adding integrity - SQLAlchemy's `JSON` column type stores the
  `model_dump_json()` output directly, and every read path immediately
  reconstructs the Pydantic object. Invoices *do* get real columns, because
  they're the thing that accumulates over time via connectors and is the
  natural unit of Contract CI history.
- **Violation Graph as a Python class, not a graph database**: at this
  dataset size (5 vendors, 60 invoices, 14 findings), a real graph DB would
  be pure ceremony. `ViolationGraph` is a thin in-memory query layer over
  `list[Finding]` - nodes and edges are just the foreign keys (`vendor_id`,
  `invoice_id`, `rule_key`) already on each `Finding`.
- **`demo_today` as a fixed reference date** (`app/config.py`): the seeded
  invoice history and contract terms are dated relative to a fixed point,
  not the real wall clock, so the Renewal Risk Calendar and Rule Inspector
  stay meaningful whenever this is actually run, rather than degrading as
  real time passes the demo data's shelf life.
