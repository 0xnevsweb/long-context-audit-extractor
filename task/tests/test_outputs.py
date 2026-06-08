"""Verifier for the long-context audit extractor CLI."""
from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

import pytest

APP_DIR = Path("/app/audit-extractor")
if not APP_DIR.exists():
    APP_DIR = Path(__file__).resolve().parents[1] / "environment" / "audit-extractor"

ARCHIVE_PATH = Path("/app/data/audit_archive.md")
if not ARCHIVE_PATH.exists():
    ARCHIVE_PATH = Path(__file__).resolve().parent / "seeds" / "audit_archive.md"

GOLDEN_DIR = Path(__file__).resolve().parent / "seeds" / "golden"
OUTPUT_DIR = Path("/app/output")
CLI = ["node", str(APP_DIR / "src" / "cli.js"), "extract"]


def _load_golden(name: str):
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def _ledger_slice(markdown: str) -> str:
    """Return markdown under the canonical ## Transaction Ledger heading only."""
    match = re.search(r"^## Transaction Ledger\s*$", markdown, re.M)
    assert match, "archive missing canonical Transaction Ledger section"
    rest = markdown[match.end() :]
    end = re.search(r"^## ", rest, re.M)
    stop = match.end() + (end.start() if end else len(rest))
    return markdown[match.start() : stop]


def _parse_emails(markdown: str) -> list[dict]:
    """Parse transaction-scoped email excerpts from the authoritative mail section."""
    start = re.search(r"^## Email Excerpts\s*$", markdown, re.M)
    end = re.search(r"^## Policy Exceptions\s*$", markdown, re.M)
    if not start or not end or end.start() <= start.start():
        return []
    slice_ = markdown[start.start() : end.start()]
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
def golden_transactions() -> list[dict]:
    """Load golden transaction rows derived from the archive."""
    return _load_golden("transactions.json")["items"]


@pytest.fixture(scope="module")
def golden_exceptions() -> list[dict]:
    """Load golden flagged transaction rows."""
    return _load_golden("exceptions.json")["items"]


@pytest.fixture(scope="module")
def golden_report() -> list[dict]:
    """Load golden reconciliation report lines."""
    path = GOLDEN_DIR / "reconciliation_report.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def golden_meta() -> dict:
    """Load golden metadata for targeted behavioral checks."""
    return _load_golden("meta.json")


@pytest.fixture(scope="module")
def pipeline_output(archive_text: str) -> Path:
    """Run the extractor once against the archive."""
    result = _run_cli(ARCHIVE_PATH, OUTPUT_DIR)
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    return OUTPUT_DIR


def test_archive_is_long_context(archive_text: str) -> None:
    """Verify the shipped handbook meets long-context size and depth requirements."""
    assert len(archive_text) >= 200_000, (
        f"archive too small for long-context task: {len(archive_text)} chars"
    )
    assert len(archive_text) // 4 >= 50_000, (
        f"archive below ~50k token estimate: {len(archive_text) // 4}"
    )
    lines = [line.strip() for line in archive_text.splitlines() if line.strip()]
    unique_ratio = len(set(lines)) / len(lines)
    assert unique_ratio >= 0.55, f"archive line repetition too high: {unique_ratio:.3f}"
    assert "Investigation Brief 01" in archive_text
    brief_09_heading = "## Investigation Brief 09 — Mid-Year Amendment"
    assert brief_09_heading in archive_text
    brief_09_at = archive_text.find(brief_09_heading)
    assert brief_09_at >= 120_000, "policy amendment should be deep in the archive"
    assert "weekly metrics" not in archive_text


def test_archive_policy_is_distributed(archive_text: str) -> None:
    """Binding rules are spread across nine briefs without single-hook grep markers."""
    for idx in range(1, 10):
        assert f"Investigation Brief {idx:02d}" in archive_text or (
            idx == 9 and "Investigation Brief 09" in archive_text
        )
    assert "binding for extract" not in archive_text
    assert "mandatory for extract" not in archive_text
    for section in (
        "## Email Excerpts",
        "## Policy Exceptions",
        "## Correction Notices",
        "## Transaction Ledger",
    ):
        assert section in archive_text, f"missing structured section {section}"


def test_cli_requires_arguments() -> None:
    """Verify that missing --input or --outdir prints to stderr and exits 1."""
    proc = subprocess.run(
        ["node", str(APP_DIR / "src" / "cli.js"), "extract"],
        cwd=str(APP_DIR),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert proc.stderr.strip()
    assert "missing" in proc.stderr.lower()


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
    pipeline_output: Path, golden_transactions: list[dict]
) -> None:
    """Verify transactions.json envelope and row fields match golden expectations."""
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    assert "items" in payload and isinstance(payload["items"], list)
    assert len(payload["items"]) == len(golden_transactions)

    for actual, exp in zip(payload["items"], golden_transactions, strict=True):
        assert actual["transaction_id"] == exp["transaction_id"]
        assert actual["owner"] == exp["owner"]
        assert actual["status"] == exp["status"]
        assert actual["effective_date"] == exp["effective_date"]
        assert abs(actual["amount_usd"] - exp["amount_usd"]) < 0.001
        assert actual.get("exception_reason") == exp.get("exception_reason")


def test_transactions_sorted(pipeline_output: Path) -> None:
    """Verify transactions.json items are sorted by transaction_id ascending."""
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    ids = [row["transaction_id"] for row in payload["items"]]
    assert ids == sorted(ids)


def test_transactions_csv_matches_json(
    pipeline_output: Path, golden_transactions: list[dict]
) -> None:
    """Verify transactions.csv header, ordering, and cell values mirror JSON rows."""
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
    assert len(rows) == len(golden_transactions)
    for actual, exp in zip(rows, golden_transactions, strict=True):
        assert actual["transaction_id"] == exp["transaction_id"]
        assert actual["owner"] == exp["owner"]
        assert actual["status"] == exp["status"]
        assert actual["effective_date"] == exp["effective_date"]
        assert float(actual["amount_usd"]) == pytest.approx(exp["amount_usd"])
        exc_cell = actual["exception_reason"]
        if exp.get("exception_reason") is None:
            assert exc_cell == ""
        else:
            assert exc_cell == exp["exception_reason"]


def test_exceptions_json_only_flagged(
    pipeline_output: Path, golden_exceptions: list[dict]
) -> None:
    """Verify exceptions.json contains only rows with non-null exception_reason."""
    payload = json.loads((pipeline_output / "exceptions.json").read_text(encoding="utf-8"))
    assert "items" in payload
    assert len(payload["items"]) == len(golden_exceptions)
    for actual, exp in zip(payload["items"], golden_exceptions, strict=True):
        assert actual["transaction_id"] == exp["transaction_id"]
        assert actual["exception_reason"] == exp["exception_reason"]


def test_exceptions_sorted_by_transaction_id(
    pipeline_output: Path,
) -> None:
    """Verify exceptions.json items are sorted by transaction_id ascending."""
    payload = json.loads((pipeline_output / "exceptions.json").read_text(encoding="utf-8"))
    ids = [row["transaction_id"] for row in payload["items"]]
    assert ids == sorted(ids)


def test_reconciliation_report(
    pipeline_output: Path, golden_report: list[dict]
) -> None:
    """Verify reconciliation_report.jsonl lines match golden correction notices."""
    lines = (pipeline_output / "reconciliation_report.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(golden_report)
    parsed = [json.loads(line) for line in lines if line.strip()]
    assert [row["notice_id"] for row in parsed] == [row["notice_id"] for row in golden_report]
    for actual, exp in zip(parsed, golden_report, strict=True):
        assert actual == exp


def test_duplicate_ledger_last_wins(
    pipeline_output: Path, archive_text: str, golden_transactions: list[dict]
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
    exp_by_id = {r["transaction_id"]: r for r in golden_transactions}
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    for tid in dup_ids:
        assert out_by_id[tid]["owner"] == exp_by_id[tid]["owner"]


def test_skips_provisional_ledger_rows(
    pipeline_output: Path,
    archive_text: str,
    golden_meta: dict,
    golden_transactions: list[dict],
) -> None:
    """Verify provisional: true ledger blocks are ignored per Brief 01."""
    tid = golden_meta["provisional_txn"]
    assert re.search(rf"^### {re.escape(tid)}\s*$[\s\S]*?^provisional:\s*true\s*$", archive_text, re.M | re.I)
    section = _ledger_slice(archive_text)
    assert section.count(f"### {tid}") >= 2
    exp = next(r for r in golden_transactions if r["transaction_id"] == tid)
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    actual = next(r for r in payload["items"] if r["transaction_id"] == tid)
    assert actual["owner"] == exp["owner"]
    assert actual["owner"] != "stale"


def test_ignores_decoy_ledger_section(
    pipeline_output: Path, archive_text: str
) -> None:
    """Verify output does not use the working-copy ledger section."""
    assert "## Transaction Ledger (working copy)" in archive_text
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    assert all(row["owner"] != "decoy" for row in payload["items"])


def test_compliance_hold_uses_pre_correction_ledger_date(
    pipeline_output: Path,
    golden_meta: dict,
    golden_transactions: list[dict],
) -> None:
    """Verify compliance_hold compares sent against ledger date before corrections adjust date."""
    tid = golden_meta["compliance_hold_txn"]
    exp = next(r for r in golden_transactions if r["transaction_id"] == tid)
    assert "compliance_hold" in (exp.get("exception_reason") or "")
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    actual = next(r for r in payload["items"] if r["transaction_id"] == tid)
    assert "compliance_hold" in (actual.get("exception_reason") or "")


def test_compliance_hold_requires_sent_line(
    pipeline_output: Path,
    archive_text: str,
) -> None:
    """Verify compliance_hold is not set from compliance@ emails lacking sent:."""
    emails = _parse_emails(archive_text)
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    for email in emails:
        if "compliance@" not in email["from_addr"].lower() or email.get("sent"):
            continue
        tid = email["transaction_id"]
        exc = out_by_id[tid].get("exception_reason") or ""
        assert "compliance_hold" not in exc


def test_non_compliance_email_does_not_change_status(
    pipeline_output: Path,
    archive_text: str,
    golden_transactions: list[dict],
) -> None:
    """Verify non-compliance@ senders never change transaction status."""
    emails = _parse_emails(archive_text)
    exp_by_id = {r["transaction_id"]: r for r in golden_transactions}
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    for email in emails:
        if "compliance@" in email["from_addr"].lower():
            continue
        tid = email["transaction_id"]
        assert out_by_id[tid]["status"] == exp_by_id[tid]["status"]


def test_retroactive_review_on_status_correction(
    pipeline_output: Path, golden_transactions: list[dict]
) -> None:
    """Verify retroactive_review is set when status was corrected to reversed above threshold."""
    flagged = [
        r for r in golden_transactions if r.get("exception_reason") and "retroactive_review" in r["exception_reason"]
    ]
    assert flagged, "fixture must include at least one retroactive_review row"
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    for exp in flagged:
        assert "retroactive_review" in (out_by_id[exp["transaction_id"]].get("exception_reason") or "")


def test_compliance_email_sent_date_gate(
    pipeline_output: Path,
    archive_text: str,
    golden_transactions: list[dict],
) -> None:
    """Verify compliance emails with sent before ledger date do not change status."""
    emails = _parse_emails(archive_text)
    section = _ledger_slice(archive_text)
    ledger_dates: dict[str, str] = {}
    for block in section.split("\n### ")[1:]:
        lines = block.splitlines()
        txn_id = lines[0].strip()
        if not txn_id.startswith("TXN-"):
            continue
        for line in lines:
            if line.strip().startswith("date:"):
                ledger_dates[txn_id] = line.split(":", 1)[1].strip()
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    exp_by_id = {r["transaction_id"]: r for r in golden_transactions}
    for email in emails:
        if "compliance@" not in email["from_addr"].lower() or not email.get("sent"):
            continue
        txn_id = email["transaction_id"]
        if txn_id not in ledger_dates or email["sent"] >= ledger_dates[txn_id]:
            continue
        assert out_by_id[txn_id]["status"] == exp_by_id[txn_id]["status"]


def test_correction_effective_date_from_handbook(
    pipeline_output: Path,
    archive_text: str,
    golden_transactions: list[dict],
) -> None:
    """Verify effective_date uses winning correction effective dates when status or date was corrected."""
    corrected_ids = set()
    slice_start = archive_text.find("## Correction Notices")
    slice_end = archive_text.find("## Transaction Ledger", slice_start)
    corr_slice = archive_text[slice_start:slice_end]
    for block in corr_slice.split("\n### ")[1:]:
        field_m = re.search(r"^field:\s*(\w+)", block, re.M)
        target_m = re.search(r"^targets:\s*(TXN-[0-9a-f-]+)", block, re.M)
        if field_m and target_m and field_m.group(1) in ("status", "date"):
            corrected_ids.add(target_m.group(1))
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    by_id = {row["transaction_id"]: row for row in payload["items"]}
    for exp in golden_transactions:
        if exp["transaction_id"] not in corrected_ids:
            continue
        assert by_id[exp["transaction_id"]]["effective_date"] == exp["effective_date"]


def test_compliance_email_without_sent_applies_status(
    pipeline_output: Path,
    archive_text: str,
    golden_transactions: list[dict],
) -> None:
    """Verify compliance emails without sent: still apply status when precedence allows."""
    emails = _parse_emails(archive_text)
    exp_by_id = {r["transaction_id"]: r for r in golden_transactions}
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    out_by_id = {r["transaction_id"]: r for r in payload["items"]}
    for email in emails:
        if "compliance@" not in email["from_addr"].lower() or email.get("sent"):
            continue
        tid = email["transaction_id"]
        assert out_by_id[tid]["status"] == exp_by_id[tid]["status"]


def test_deterministic_rerun() -> None:
    """Verify two consecutive CLI runs produce identical transactions.json."""
    tmp = Path("/tmp/audit-extract-rerun")
    first = _run_cli(ARCHIVE_PATH, tmp / "first")
    second = _run_cli(ARCHIVE_PATH, tmp / "second")
    assert first.returncode == 0 and second.returncode == 0
    a = (tmp / "first" / "transactions.json").read_text(encoding="utf-8")
    b = (tmp / "second" / "transactions.json").read_text(encoding="utf-8")
    assert a == b


def test_meeting_signed_owner_override(
    pipeline_output: Path, archive_text: str, golden_transactions: list[dict]
) -> None:
    """Verify signed meeting amendments with valid effective dates change owner."""
    exp_by_id = {r["transaction_id"]: r for r in golden_transactions}
    payload = json.loads((pipeline_output / "transactions.json").read_text(encoding="utf-8"))
    by_id = {row["transaction_id"]: row for row in payload["items"]}
    for match in re.finditer(r"^#### Amendment for (TXN-[0-9a-f-]+)\s*$", archive_text, re.M):
        block = archive_text[match.start() : match.start() + 500]
        signed_m = re.search(r"^signed:\s*(.+)$", block, re.M)
        effective_m = re.search(r"^effective:\s*(\d{4}-\d{2}-\d{2})\s*$", block, re.M)
        if not signed_m or signed_m.group(1).strip().lower() != "true":
            continue
        tid = match.group(1)
        if effective_m and effective_m.group(1) < "2024-01-01":
            continue
        assert by_id[tid]["owner"] == exp_by_id[tid]["owner"]
