# LedgerHawk

**CI/CD for Enterprise Contracts.** Contracts get compiled into executable
pricing rules. Invoices get run against those rules like test cases. An
overcharge shows up the way a failing test does: the exact clause, the
exact math, and proof.

## Status: early build (day 1)

This is the foundation, not the finished product yet. What's here today:

- **Contract AST** (`api/app/schemas/ast.py`) - a typed intermediate
  representation of a contract's obligations: parties, term, pricing
  clauses, each traced back to a verbatim clause quote. See
  [docs/AST.md](docs/AST.md).
- **Pricing DSL** (`api/app/schemas/dsl.py`) - the executable, lowered
  form: flat fees, per-unit rates, volume tiers, escalation caps,
  proration policy, credits. See [docs/DSL.md](docs/DSL.md).
- **Billing Engine** (`api/app/pipeline/billing_engine.py`) - the
  deterministic core: plain `Decimal` arithmetic, no LLM anywhere near it.
  Handles tiered pricing, daily proration (including leap years), capped
  escalation, and credit rollover. Fully unit-tested.
- **Precedence Resolver** (`api/app/pipeline/precedence.py`) - resolves
  which document's version of a rule wins when a contract spans an MSA,
  amendments, and an executed email, as of any given date.

## Design law

LLMs will only ever translate contract language into these structured
artifacts (the AST, the DSL). They never compute a dollar figure. That's
what the Billing Engine is for, and it's why it has no LLM dependency at
all - every number it produces comes from a plain, unit-tested function
multiplying a rate by a quantity.

## Running the tests

```bash
cd api
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
python -m pytest -q
```

## What's next

Reconciliation against real invoices, a violation graph, a forecast
engine, contract unit tests, and an API + dashboard on top of this. This
README will grow with the project.

## License

MIT - see [LICENSE](LICENSE).
