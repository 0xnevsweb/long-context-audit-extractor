#!/usr/bin/env python3
"""Write golden verifier fixtures from the reference expected builder."""

from __future__ import annotations

import json
from pathlib import Path

from expected_builder import build_expected, rows_to_json_items

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "environment" / "audit-extractor" / "data" / "audit_archive.md"
GOLDEN = ROOT / "tests" / "seeds" / "golden"


def main() -> None:
    markdown = ARCHIVE.read_text(encoding="utf-8")
    rows, report = build_expected(markdown)
    flagged = [row for row in rows if row.exception_reason]

    GOLDEN.mkdir(parents=True, exist_ok=True)
    (GOLDEN / "transactions.json").write_text(
        json.dumps({"items": rows_to_json_items(rows)}, indent=2) + "\n",
        encoding="utf-8",
    )
    (GOLDEN / "exceptions.json").write_text(
        json.dumps({"items": rows_to_json_items(flagged)}, indent=2) + "\n",
        encoding="utf-8",
    )
    report_body = "\n".join(json.dumps(line) for line in report)
    (GOLDEN / "reconciliation_report.jsonl").write_text(
        f"{report_body}\n" if report_body else "",
        encoding="utf-8",
    )
    meta = {
        "transaction_count": len(rows),
        "flagged_count": len(flagged),
        "report_line_count": len(report),
        "provisional_txn": "TXN-ba9e6ade-67ce-5a61-b097-ab0d34f8e6bb",
        "compliance_hold_txn": "TXN-1b083448-63e3-5527-a20a-edd71416341c",
    }
    (GOLDEN / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"wrote golden fixtures to {GOLDEN}")


if __name__ == "__main__":
    main()
