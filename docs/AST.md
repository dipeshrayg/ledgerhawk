# Contract AST

The Contract AST is LedgerHawk's typed intermediate representation of a
contract's obligations. It sits between raw text and the executable Pricing
DSL - see [`api/app/schemas/ast.py`](../api/app/schemas/ast.py) for the
Pydantic source of truth.

## Why an AST at all

A contract is not one document - it's an MSA plus amendments plus maybe an
executed email. The AST is where those documents get merged into one
coherent picture of "what are the rules right now," with each fact still
pointing back at the paragraph it came from. Nothing past this layer ever
re-reads the source text.

## Shape

```
ContractAST
├── contract_id, vendor_name
├── parties: [Party]                 # name + role (vendor/customer)
├── documents: [DocumentRef]         # MSA, AMENDMENT, EMAIL, ORDER_FORM, PROPOSAL
│     each: doc_id, effective_date, executed: bool, authority_rank: int
├── term: ContractTerm               # start/end, renewal_type, notice_days, uplift_pct
└── pricing_clauses: [PricingClause]
      each: clause_type, rule_key, doc_id, effective_from/to, provenance, params
```

## `DocumentRef` and precedence inputs

Every document contributing terms is registered with:

- `effective_date` - when its terms take effect
- `executed` - `False` for drafts/pending offers; only executed documents can
  win precedence
- `authority_rank` - tiebreaker when two documents share an effective_date
  (used for same-day amendment vs. email edge cases)

The precedence *algorithm* itself lives in the DSL layer
(`app/pipeline/precedence.py`) - the AST only carries the raw ingredients.

## `PricingClause.rule_key`

This is the field that makes multi-document contracts tractable. Two clauses
from different documents that govern the *same economic fact* (e.g. the
per-seat rate) share a `rule_key` like `pricing.per_unit.seat`. The
precedence resolver groups by `rule_key` and picks one winner per group as of
any query date. Convention: `<category>.<clause_type>.<subject>`, e.g.:

- `pricing.per_unit.seat`
- `pricing.discount.default`
- `pricing.escalation.default`
- `pricing.credit.rollover`

## `Provenance` - the non-negotiable field

```python
class Provenance(BaseModel):
    doc_id: str
    section: str
    quote: str   # verbatim, never paraphrased
    page: int | None
```

Every clause, term, and (downstream) every DSL rule carries one of these.
The Evidence Generator (§ Violation Graph) refuses to synthesize a finding
without a `quote` - this is the mechanism behind LedgerHawk's core design
law: *LLMs translate language into structure; they never originate a dollar
figure.*

## Example

```json
{
  "contract_id": "megacloud",
  "vendor_name": "MegaCloud Inc.",
  "documents": [
    {"doc_id": "msa", "name": "Master Services Agreement", "doc_type": "MSA",
     "effective_date": "2024-01-01", "executed": true, "authority_rank": 0},
    {"doc_id": "amend2", "name": "Amendment 2", "doc_type": "AMENDMENT",
     "effective_date": "2025-01-01", "executed": true, "authority_rank": 1},
    {"doc_id": "email1", "name": "Email Agreement (discount extension)",
     "doc_type": "EMAIL", "effective_date": "2025-06-01", "executed": true,
     "authority_rank": 2}
  ],
  "pricing_clauses": [
    {
      "clause_id": "msa-6.2", "clause_type": "per_unit",
      "rule_key": "pricing.per_unit.seat", "doc_id": "msa",
      "effective_from": "2024-01-01",
      "provenance": {"doc_id": "msa", "section": "6.2",
        "quote": "Customer shall pay $15.00 per active seat per month."},
      "params": {"unit_name": "seat", "rate": "15.00"}
    }
  ]
}
```

See [`docs/DEMO_DATA.md`](DEMO_DATA.md) for the full MegaCloud AST, including
the amendment chain and the email-agreement precedence case.
