"""Verifier for the long-context audit extractor CLI."""
from __future__ import annotations

import csv
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

APP_DIR = Path("/app/audit-extractor")
if not APP_DIR.exists():
    APP_DIR = Path(__file__).resolve().parents[1] / "environment" / "audit-extractor"

ARCHIVE_PATH = Path("/app/data/audit_archive.md")
if not ARCHIVE_PATH.exists():
    ARCHIVE_PATH = Path(__file__).resolve().parent / "seeds" / "audit_archive.md"

OUTPUT_DIR = Path("/app/output")
CLI = ["node", str(APP_DIR / "src" / "cli.js"), "extract"]

STATUS_ORDER = {"pending": 0, "approved": 1, "rejected": 2, "reversed": 3}


@dataclass(frozen=True)
class TransactionRow:
    transaction_id: str
    owner: str
    status: str
    effective_date: str
    amount_usd: float
    exception_reason: str | None


def _section_between(markdown: str, start_heading: str, end_heading: str) -> str:
    """Return markdown from a line-anchored ## heading up to the next line-anchored ## heading."""
    start = re.search(rf"^{re.escape(start_heading)}\s*$", markdown, re.M)
    if not start:
        return ""
    rest = markdown[start.end() :]
    end = re.search(rf"^{re.escape(end_heading)}\s*$", rest, re.M)
    stop = start.end() + (end.start() if end else len(rest))
    return markdown[start.start() : stop]


def _ledger_slice(markdown: str) -> str:
    """Return markdown under the canonical ## Transaction Ledger heading only."""
    match = re.search(r"^## Transaction Ledger\s*$", markdown, re.M)
    assert match, "archive missing canonical Transaction Ledger section"
    rest = markdown[match.end() :]
    end = re.search(r"^## ", rest, re.M)
    stop = match.end() + (end.start() if end else len(rest))
    return markdown[match.start() : stop]


def _parse_ledger(markdown: str) -> dict[str, dict]:
    """Parse ledger blocks; skip provisional rows; last non-provisional block wins."""
    section = _ledger_slice(markdown)
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


def _parse_meetings(markdown: str) -> list[dict]:
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


def _parse_emails(markdown: str) -> list[dict]:
    slice_ = _section_between(markdown, "## Email Excerpts", "## Policy Exceptions")
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


def _parse_corrections(markdown: str) -> list[dict]:
    slice_ = _section_between(markdown, "## Correction Notices", "## Transaction Ledger")
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


def _parse_policy_waiver_ids(markdown: str) -> set[str]:
    slice_ = _section_between(markdown, "## Policy Exceptions", "## Correction Notices")
    ids: set[str] = set()
    for block in slice_.split("### Policy Exception"):
        txn_m = re.search(r"^transaction:\s*(TXN-[0-9a-f-]+)\s*$", block, re.M)
        appr_m = re.search(r"^approved_by:\s*(\S+)\s*$", block, re.M)
        if txn_m and appr_m and appr_m.group(1).strip().lower() == "compliance":
            ids.add(txn_m.group(1))
    return ids


def _build_expected(markdown: str) -> tuple[list[TransactionRow], list[dict]]:
    by_id = _parse_ledger(markdown)
    meetings = _parse_meetings(markdown)
    emails = _parse_emails(markdown)
    corrections = _parse_corrections(markdown)
    policy_ok = _parse_policy_waiver_ids(markdown)

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
        if status == "rejected" and any(
            "compliance@" in em["from_addr"].lower()
            and em["transaction_id"] == tid
            and em.get("sent")
            and em["sent"] >= ledger_date
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


def _run_cli(archive: Path, outdir: Path) -> subprocess.CompletedProcess[str]:
    outdir.mkdir(parents=True, exist_ok=True)
    for path in outdir.iterdir():
        if path.is_file():
            path.unlink()
    return subprocess.run(
        [*CLI, "--input", str(archive), "--outdir", str(outdir)],
        cwd=str(APP_DIR),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def archive_text() -> str:
    """Load the protected audit archive used for verification."""
    return ARCHIVE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def expected(archive_text: str) -> tuple[list[TransactionRow], list[dict]]:
    """Compute handbook-correct expected rows from the archive."""
    return _build_expected(archive_text)


@pytest.fixture(scope="module")
def pipeline_output(archive_text: str) -> Path:
    """Run the extractor once against the archive."""
    result = _run_cli(ARCHIVE_PATH, OUTPUT_DIR)
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    return OUTPUT_DIR


def test_archive_is_long_context(archive_text: str) -> None:
    """Verify that the audit archive meets the long-context size requirement."""
    assert len(archive_text) >= 200_000, (
        f"archive too small for long-context task: {len(archive_text)} chars"
    )


def test_cli_requires_arguments() -> None:
    """Verify that missing --input or --outdir yields exit code 1."""
    proc = subprocess.run(
        ["node", str(APP_DIR / "src" / "cli.js"), "extract"],
        cwd=str(APP_DIR),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1


def test_output_files_exist(pipeline_output: Path) -> None:
    """Verify that all four required output artifacts are created."""
    for name in (
        "transactions.json",
        "transactions.csv",
        "exceptions.json",
        "reconciliation_report.jsonl",
    ):
        assert (pipeline_output / name).is_file(), f"missing {name}"


def test_transactions_json_schema(
    pipeline_output: Path, expected: tuple[list[TransactionRow], list[dict]]
) -> None:
    """Verify transactions.json envelope and row fields match the handbook."""
    expected_rows, _ = expected
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    assert "items" in payload and isinstance(payload["items"], list)
    assert len(payload["items"]) == len(expected_rows)

    for actual, exp in zip(payload["items"], expected_rows, strict=True):
        assert actual["transaction_id"] == exp.transaction_id
        assert actual["owner"] == exp.owner
        assert actual["status"] == exp.status
        assert actual["effective_date"] == exp.effective_date
        assert abs(actual["amount_usd"] - exp.amount_usd) < 0.001
        assert actual.get("exception_reason") == exp.exception_reason


def test_transactions_sorted(pipeline_output: Path) -> None:
    """Verify transactions.json items are sorted by transaction_id ascending."""
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    ids = [row["transaction_id"] for row in payload["items"]]
    assert ids == sorted(ids)


def test_transactions_csv_matches_json(
    pipeline_output: Path, expected: tuple[list[TransactionRow], list[dict]]
) -> None:
    """Verify transactions.csv header, ordering, and cell values mirror JSON rows."""
    expected_rows, _ = expected
    with (pipeline_output / "transactions.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "transaction_id",
            "owner",
            "status",
            "effective_date",
            "amount_usd",
            "exception_reason",
        ]
        rows = list(reader)
    assert len(rows) == len(expected_rows)
    for actual, exp in zip(rows, expected_rows, strict=True):
        assert actual["transaction_id"] == exp.transaction_id
        assert actual["owner"] == exp.owner
        assert actual["status"] == exp.status
        assert actual["effective_date"] == exp.effective_date
        assert float(actual["amount_usd"]) == pytest.approx(exp.amount_usd)
        exc_cell = actual["exception_reason"]
        if exp.exception_reason is None:
            assert exc_cell == ""
        else:
            assert exc_cell == exp.exception_reason


def test_exceptions_json_only_flagged(
    pipeline_output: Path, expected: tuple[list[TransactionRow], list[dict]]
) -> None:
    """Verify exceptions.json contains only rows with non-null exception_reason."""
    expected_rows, _ = expected
    flagged = [row for row in expected_rows if row.exception_reason]
    payload = json.loads((pipeline_output / "exceptions.json").read_text(encoding="utf-8"))
    assert "items" in payload
    assert len(payload["items"]) == len(flagged)
    for actual, exp in zip(payload["items"], flagged, strict=True):
        assert actual["transaction_id"] == exp.transaction_id
        assert actual["exception_reason"] == exp.exception_reason


def test_reconciliation_report(
    pipeline_output: Path, expected: tuple[list[TransactionRow], list[dict]]
) -> None:
    """Verify reconciliation_report.jsonl lines match winning correction notices."""
    _, expected_report = expected
    lines = (pipeline_output / "reconciliation_report.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(expected_report)
    parsed = [json.loads(line) for line in lines if line.strip()]
    assert [row["notice_id"] for row in parsed] == [row["notice_id"] for row in expected_report]
    for actual, exp in zip(parsed, expected_report, strict=True):
        assert actual == exp


def test_duplicate_ledger_last_wins(
    pipeline_output: Path, archive_text: str, expected: tuple[list[TransactionRow], list[dict]]
) -> None:
    """Verify duplicate ledger blocks use the last non-provisional occurrence in file order."""
    section = _ledger_slice(archive_text)
    dup_ids: list[str] = []
    seen: set[str] = set()
    for block in section.split("\n### ")[1:]:
        txn_id = block.splitlines()[0].strip()
        if not txn_id.startswith("TXN-"):
            continue
        if txn_id in seen:
            dup_ids.append(txn_id)
        seen.add(txn_id)
    assert dup_ids, "fixture should include duplicate ledger rows"
    exp_by_id = {r.transaction_id: r for r in expected[0]}
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    for tid in dup_ids:
        assert out_by_id[tid]["owner"] == exp_by_id[tid].owner


def test_ignores_decoy_ledger_section(
    pipeline_output: Path, archive_text: str, expected: tuple[list[TransactionRow], list[dict]]
) -> None:
    """Verify output does not use the working-copy ledger section."""
    assert "## Transaction Ledger (working copy)" in archive_text
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    assert all(row["owner"] != "decoy" for row in payload["items"])


def test_compliance_hold_requires_sent_line(
    pipeline_output: Path,
    archive_text: str,
    expected: tuple[list[TransactionRow], list[dict]],
) -> None:
    """Verify compliance_hold is not set from compliance@ emails lacking sent:."""
    emails = _parse_emails(archive_text)
    ledger = _parse_ledger(archive_text)
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    for email in emails:
        if "compliance@" not in email["from_addr"].lower() or email.get("sent"):
            continue
        tid = email["transaction_id"]
        if tid not in ledger:
            continue
        exc = out_by_id[tid].get("exception_reason") or ""
        assert "compliance_hold" not in exc


def test_retroactive_review_on_status_correction(
    pipeline_output: Path, expected: tuple[list[TransactionRow], list[dict]]
) -> None:
    """Verify retroactive_review is set when status was corrected to reversed above threshold."""
    flagged = [r for r in expected[0] if r.exception_reason and "retroactive_review" in r.exception_reason]
    if not flagged:
        pytest.skip("no retroactive_review rows in fixture")
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    for exp in flagged:
        assert "retroactive_review" in (out_by_id[exp.transaction_id].get("exception_reason") or "")


def test_compliance_email_without_sent_applies_status(
    pipeline_output: Path,
    archive_text: str,
    expected: tuple[list[TransactionRow], list[dict]],
) -> None:
    """Verify compliance emails without sent: still apply status when precedence allows."""
    emails = _parse_emails(archive_text)
    exp_by_id = {r.transaction_id: r for r in expected[0]}
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    for email in emails:
        if "compliance@" not in email["from_addr"].lower() or email.get("sent"):
            continue
        tid = email["transaction_id"]
        assert out_by_id[tid]["status"] == exp_by_id[tid].status


def test_compliance_email_sent_date_gate(
    pipeline_output: Path,
    archive_text: str,
    expected: tuple[list[TransactionRow], list[dict]],
) -> None:
    """Verify compliance emails with sent before ledger date do not change status."""
    emails = _parse_emails(archive_text)
    ledger = _parse_ledger(archive_text)
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    exp_by_id = {r.transaction_id: r for r in expected[0]}
    for email in emails:
        if "compliance@" not in email["from_addr"].lower():
            continue
        if not email.get("sent"):
            continue
        txn_id = email["transaction_id"]
        if email["sent"] >= ledger[txn_id]["date"]:
            continue
        assert out_by_id[txn_id]["status"] == exp_by_id[txn_id].status


def test_deterministic_rerun() -> None:
    """Verify two consecutive CLI runs produce identical transactions.json."""
    tmp = Path("/tmp/audit-extract-rerun")
    first = _run_cli(ARCHIVE_PATH, tmp / "first")
    second = _run_cli(ARCHIVE_PATH, tmp / "second")
    assert first.returncode == 0 and second.returncode == 0
    a = (tmp / "first" / "transactions.json").read_text(encoding="utf-8")
    b = (tmp / "second" / "transactions.json").read_text(encoding="utf-8")
    assert a == b


def test_correction_effective_date_from_handbook(
    pipeline_output: Path,
    archive_text: str,
    expected: tuple[list[TransactionRow], list[dict]],
) -> None:
    """Verify effective_date uses winning correction effective dates when status or date was corrected."""
    expected_rows, _ = expected
    corrections = _parse_corrections(archive_text)
    date_or_status_corrected = {
        c["transaction_id"] for c in corrections if c["field"] in ("status", "date")
    }
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    by_id = {row["transaction_id"]: row for row in payload["items"]}
    for exp in expected_rows:
        if exp.transaction_id not in date_or_status_corrected:
            continue
        assert by_id[exp.transaction_id]["effective_date"] == exp.effective_date


def test_meeting_signed_owner_override(
    pipeline_output: Path, archive_text: str, expected: tuple[list[TransactionRow], list[dict]]
) -> None:
    """Verify signed meeting amendments with valid effective dates change owner."""
    meetings = _parse_meetings(archive_text)
    ledger = _parse_ledger(archive_text)
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    by_id = {row["transaction_id"]: row for row in payload["items"]}
    exp_by_id = {r.transaction_id: r for r in expected[0]}

    for meeting in meetings:
        if not meeting["signed"]:
            continue
        if meeting["effective"] and meeting["effective"] < ledger[meeting["transaction_id"]]["date"]:
            continue
        assert by_id[meeting["transaction_id"]]["owner"] == exp_by_id[meeting["transaction_id"]].owner
