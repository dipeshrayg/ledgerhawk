"""Verifies that every Provenance.quote in every vendor's ast.json fixture
appears verbatim in that vendor's source contract text. This is the
mechanical check behind LedgerHawk's core design law: every finding traces
to a real clause, never a paraphrase or a hallucination."""
import json
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
VENDORS_TXT = Path(__file__).resolve().parents[1] / "data" / "vendors"


def normalize(s):
    return " ".join(s.split())


def main():
    failures = []
    checked = 0
    for vendor_dir in sorted(FIXTURES.iterdir()):
        if not vendor_dir.is_dir():
            continue
        ast_path = vendor_dir / "ast.json"
        if not ast_path.exists():
            continue
        ast = json.loads(ast_path.read_text())
        vendor_txt_dir = VENDORS_TXT / vendor_dir.name
        if not vendor_txt_dir.exists():
            continue
        full_text = normalize(" ".join(p.read_text(encoding="utf-8") for p in vendor_txt_dir.glob("*.txt")))

        quotes = [ast["term"]["provenance"]["quote"]]
        quotes += [c["provenance"]["quote"] for c in ast.get("pricing_clauses", [])]
        dsl = json.loads((vendor_dir / "dsl.json").read_text())
        quotes += [r["provenance"]["quote"] for r in dsl.get("rules", [])]

        for q in quotes:
            checked += 1
            if normalize(q) not in full_text:
                failures.append((vendor_dir.name, q))

    print(f"Checked {checked} clause quotes across {len(list(FIXTURES.iterdir()))} vendors.")
    if failures:
        print(f"FAILED: {len(failures)} quotes not found verbatim in source text:")
        for vendor, q in failures:
            print(f"  [{vendor}] {q!r}")
        sys.exit(1)
    print("All quotes verified verbatim in source contract text.")


if __name__ == "__main__":
    main()
