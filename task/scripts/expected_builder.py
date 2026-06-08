#!/usr/bin/env python3
"""Reference expected outputs for the audit extractor (not mounted in the agent image)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

STATUS_ORDER = {"pending": 0, "approved": 1, "rejected": 2, "reversed": 3}


@dataclass(frozen=True)
class TransactionRow:
    transaction_id: str
    owner: str
    status: str
    effective_date: str
    amount_usd: float
    exception_reason: str | None


def section_between(markdown: str, start_heading: str, end_heading: str) -> str:
    start = re.search(rf"^{re.escape(start_heading)}\s*$", markdown, re.M)
    if not start:
        return ""
    rest = markdown[start.end() :]
    end = re.search(rf"^{re.escape(end_heading)}\s*$", rest, re.M)
    stop = start.end() + (end.start() if end else len(rest))
    return markdown[start.start() : stop]


def ledger_slice(markdown: str) -> str:
    match = re.search(r"^## Transaction Ledger\s*$", markdown, re.M)
    if not match:
        raise ValueError("archive missing canonical Transaction Ledger section")
    rest = markdown[match.end() :]
    end = re.search(r"^## ", rest, re.M)
    stop = match.end() + (end.start() if end else len(rest))
    return markdown[match.start() : stop]


def parse_ledger(markdown: str) -> dict[str, dict]:
    section = ledger_slice(markdown)
    by_id: dict[str, dict] = {}
    for block in section.split("\n### ")[1:]:
        lines = block.splitlines()
        txn_id = lines[0].strip()
        if not txn_id.startswith("TXN-"):
            continue
        if re.search(r"^provisional:\s*true\s*$", block, re.M | re.I):
            continue
        row = {"transaction_id": txn_id}
        for line in lines:
            trimmed = line.strip()
            if trimmed.startswith("amount:"):
                row["amount"] = float(trimmed.split(":", 1)[1].strip())
            elif trimmed.startswith("owner:"):
                row["owner"] = trimmed.split(":", 1)[1].strip()
            elif trimmed.startswith("status:"):
                row["status"] = trimmed.split(":", 1)[1].strip()
            elif trimmed.startswith("date:"):
                row["date"] = trimmed.split(":", 1)[1].strip()
        by_id[txn_id] = row
    return by_id


def parse_meetings(markdown: str) -> list[dict]:
    meetings: list[dict] = []
    for match in re.finditer(r"^#### Amendment for (TXN-[0-9a-f-]+)\s*$", markdown, re.M):
        block = markdown[match.start() : match.start() + 500]
        owner_m = re.search(r"^owner:\s*(.+)$", block, re.M)
        signed_m = re.search(r"^signed:\s*(.+)$", block, re.M)
        effective_m = re.search(r"^effective:\s*(\d{4}-\d{2}-\d{2})\s*$", block, re.M)
        meetings.append(
            {
                "transaction_id": match.group(1),
                "owner": owner_m.group(1).strip() if owner_m else "",
                "signed": signed_m.group(1).strip().lower() == "true" if signed_m else False,
                "effective": effective_m.group(1) if effective_m else None,
            }
        )
    return meetings


def parse_emails(markdown: str) -> list[dict]:
    slice_ = section_between(markdown, "## Email Excerpts", "## Policy Exceptions")
    if not slice_:
        slice_ = markdown
    emails: list[dict] = []
    for block in slice_.split("\n\n"):
        from_m = re.search(r"^From:\s*(.+)$", block, re.M)
        subj_m = re.search(r"^Subject:\s*Re:\s*(TXN-[0-9a-f-]+)", block, re.M)
        status_m = re.search(r"^status:\s*(\w+)", block, re.M)
        sent_m = re.search(r"^sent:\s*(\d{4}-\d{2}-\d{2})\s*$", block, re.M)
        if from_m and subj_m and status_m:
            emails.append(
                {
                    "from_addr": from_m.group(1).strip(),
                    "transaction_id": subj_m.group(1),
                    "status": status_m.group(1).lower(),
                    "sent": sent_m.group(1) if sent_m else None,
                }
            )
    return emails


def parse_corrections(markdown: str) -> list[dict]:
    slice_ = section_between(markdown, "## Correction Notices", "## Transaction Ledger")
    notices: list[dict] = []
    for block in slice_.split("\n### ")[1:]:
        lines = block.splitlines()
        notice_id = lines[0].strip()
        if not notice_id.startswith("CORR-"):
            continue
        entry = {"notice_id": notice_id}
        for line in lines:
            trimmed = line.strip()
            if trimmed.startswith("targets:"):
                entry["transaction_id"] = trimmed.split(":", 1)[1].strip()
            elif trimmed.startswith("field:"):
                entry["field"] = trimmed.split(":", 1)[1].strip()
            elif trimmed.startswith("value:"):
                entry["value"] = trimmed.split(":", 1)[1].strip()
            elif trimmed.startswith("effective:"):
                entry["effective"] = trimmed.split(":", 1)[1].strip()
        notices.append(entry)
    return notices


def parse_policy_waiver_ids(markdown: str) -> set[str]:
    slice_ = section_between(markdown, "## Policy Exceptions", "## Correction Notices")
    ids: set[str] = set()
    for block in slice_.split("### Policy Exception"):
        txn_m = re.search(r"^transaction:\s*(TXN-[0-9a-f-]+)\s*$", block, re.M)
        appr_m = re.search(r"^approved_by:\s*(\S+)\s*$", block, re.M)
        if txn_m and appr_m and appr_m.group(1).strip().lower() == "compliance":
            ids.add(txn_m.group(1))
    return ids


def build_expected(markdown: str) -> tuple[list[TransactionRow], list[dict]]:
    by_id = parse_ledger(markdown)
    meetings = parse_meetings(markdown)
    emails = parse_emails(markdown)
    corrections = parse_corrections(markdown)
    policy_ok = parse_policy_waiver_ids(markdown)

    for meeting in meetings:
        target = by_id.get(meeting["transaction_id"])
        if not target or not meeting["signed"]:
            continue
        if meeting["effective"] and meeting["effective"] < target["date"]:
            continue
        target["owner"] = meeting["owner"]

    for email in emails:
        target = by_id.get(email["transaction_id"])
        if not target:
            continue
        if "compliance@" not in email["from_addr"].lower():
            continue
        if email["sent"] and email["sent"] < target["date"]:
            continue
        cur = target["status"].lower()
        nxt = email["status"]
        if STATUS_ORDER.get(nxt, -1) > STATUS_ORDER.get(cur, -1):
            target["status"] = nxt

    pre_correction_dates = {tid: row["date"] for tid, row in by_id.items()}

    report: list[dict] = []
    corr_by_txn: dict[str, list[dict]] = {}
    for notice in corrections:
        corr_by_txn.setdefault(notice["transaction_id"], []).append(notice)

    corr_eff_date: dict[str, str] = {}
    status_corrected: set[str] = set()
    for tid, notices in corr_by_txn.items():
        target = by_id.get(tid)
        if not target:
            continue
        by_field: dict[str, list[dict]] = {}
        for notice in notices:
            by_field.setdefault(notice["field"], []).append(notice)
        effs: list[str] = []
        for field, group in by_field.items():
            winner = max(group, key=lambda x: x["effective"])
            if field == "date":
                prev = target["date"]
            elif field == "owner":
                prev = target["owner"]
            else:
                prev = target["status"]
            new_val = winner["value"]
            if field == "owner":
                target["owner"] = new_val
            elif field == "status":
                target["status"] = new_val
                status_corrected.add(tid)
                effs.append(winner["effective"])
            elif field == "date":
                target["date"] = new_val
                effs.append(winner["effective"])
            report.append(
                {
                    "notice_id": winner["notice_id"],
                    "transaction_id": tid,
                    "field": field,
                    "previous_value": str(prev),
                    "new_value": str(new_val),
                    "effective": winner["effective"],
                }
            )
        if effs:
            corr_eff_date[tid] = max(effs)

    report.sort(key=lambda r: r["notice_id"])

    rows: list[TransactionRow] = []
    for tid in sorted(by_id.keys()):
        row = by_id[tid]
        amount = float(row["amount"])
        status = row["status"].lower()
        ledger_date = row["date"]
        reasons: list[str] = []
        if amount > 10000:
            reasons.append("over_limit")
        hold_compare_date = pre_correction_dates.get(tid, ledger_date)
        if status == "rejected" and any(
            "compliance@" in em["from_addr"].lower()
            and em["transaction_id"] == tid
            and em.get("sent")
            and em["sent"] >= hold_compare_date
            for em in emails
        ):
            reasons.append("compliance_hold")
        if status == "approved" and amount > 10000 and tid in policy_ok:
            reasons.append("policy_waiver")
        if status == "reversed" and amount > 5000 and tid in status_corrected:
            reasons.append("retroactive_review")
        reasons.sort()
        rows.append(
            TransactionRow(
                transaction_id=tid,
                owner=row["owner"],
                status=status,
                effective_date=corr_eff_date.get(tid, ledger_date),
                amount_usd=round(amount, 2),
                exception_reason=";".join(reasons) if reasons else None,
            )
        )
    return rows, report


def rows_to_json_items(rows: list[TransactionRow]) -> list[dict]:
    return [asdict(row) for row in rows]


def main() -> None:
    archive = Path(__file__).resolve().parents[1] / "environment" / "audit-extractor" / "data" / "audit_archive.md"
    markdown = archive.read_text(encoding="utf-8")
    rows, report = build_expected(markdown)
    print(f"transactions: {len(rows)}")
    print(f"flagged: {sum(1 for r in rows if r.exception_reason)}")
    print(f"report lines: {len(report)}")


if __name__ == "__main__":
    main()
