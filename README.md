# LedgerHawk

**CI/CD for Enterprise Contracts.** Contracts get compiled into executable
pricing rules. Invoices get run against those rules like test cases. An
overcharge shows up the way a failing test does: the exact clause, the
exact math, and proof.

## Status: backend complete (day 2)

The full compiler pipeline, a seeded five-vendor demo dataset, and a
FastAPI backend are in place. No frontend yet - that's next.

### The compiler pipeline

- **Contract AST** (`api/app/schemas/ast.py`) / **Pricing DSL**
  (`api/app/schemas/dsl.py`) - typed artifacts between every stage. See
  [docs/AST.md](docs/AST.md) and [docs/DSL.md](docs/DSL.md).
- **Static Validator** (`app/pipeline/validator.py`) - lints for uncapped
  escalation, missing proration policy, conflicting rules, short
  auto-renewal notice.
- **Precedence Resolver** (`app/pipeline/precedence.py`) - resolves which
  document (MSA, amendment, executed email) governs a rule as of any date.
- **Billing Engine** (`app/pipeline/billing_engine.py`) - the deterministic
  core. Plain `Decimal` arithmetic, no LLM anywhere near it.
- **Reconciliation + Evidence Generator** - replays invoices against the
  compiled contract, produces a `Finding` per discrepancy: clause quote,
  math trace, dollar delta.
- **Violation Graph** - queryable index over vendors/clauses/findings.
- **Forecast** - deterministic 36-month replay (escalations, discount
  expiries, renewal uplifts). No ML - contract replay.
- **Diff Engine** - "git diff for contracts": categorized rule changes
  between two compiled contract versions, with a dollar-impact estimate.
- **Contract Test Runner** - YAML scenario/invariant assertions against
  the compiled DSL.
- **Audit Copilot** - natural-language questions answered from the
  Violation Graph, never free-generated.
- **Multi-agent layer** (`app/agents/`) - Contract/Pricing/Risk/
  Negotiation/Report agents, each with a deterministic fallback so the
  whole thing runs identically with zero API keys.
- **Connector SDK** (`app/connectors/`) - MockERP streaming connector, CSV
  drop-folder watcher, optional Stripe sandbox stub.

Full pipeline + architecture writeup: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### The demo dataset

Five vendors, twelve months of invoices each, 14 planted billing
discrepancies (seat drift, a double-billed fee, an expired discount a
vendor ignored, an escalation miscalculated from the wrong start date...),
reconciled with zero false positives on the clean invoices. Every planted
issue is documented with its expected dollar delta in
[docs/DEMO_DATA.md](docs/DEMO_DATA.md) - that file is the source of truth
the end-to-end test is checked against.

Regenerate it yourself:

```bash
cd api
python scripts/generate_seed_data.py    # writes data/fixtures/, data/proposal/, data/diff_pair/
python scripts/generate_seed_pdfs.py    # renders data/vendors/*/*.pdf from the .txt originals
python scripts/verify_quotes.py         # asserts every clause quote is verbatim in source text
```

## Design law

LLMs only ever translate contract language into structured artifacts (the
AST, the DSL). They never compute a dollar figure. Every number traces
back to a plain, unit-tested function multiplying a rate by a quantity -
`api/app/pipeline/billing_engine.py`, no LLM calls anywhere in it.

## Running it

```bash
cd api
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
python -m pytest -q                                # full test suite
./.venv/Scripts/uvicorn app.main:app --reload       # API at http://localhost:8000
```

The API seeds its own SQLite database from the checked-in fixtures on
startup - no API key needed. Try `http://localhost:8000/api/health` and
`http://localhost:8000/api/dashboard`.

## What's next

A React dashboard on top of this API, CI, and deployment. This README
will grow with the project.

## License

MIT - see [LICENSE](LICENSE).
