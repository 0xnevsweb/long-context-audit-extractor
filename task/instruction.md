Finance QA says the FY24 audit extractor at `/app/audit-extractor` is reconciling `/app/data/audit_archive.md` wrong — statuses drift between reruns, compliance holds miss later mail, and correction notices land on the wrong ledger rows. The input is one large FY24 audit handbook at `/app/data/audit_archive.md` (investigation briefs, committee minutes, mail excerpts, policy exceptions, correction notices, and ledger rows).

Binding reconciliation policy is distributed across Investigation Briefs 01–09, including a mid-year amendment in Brief 09 that overrides earlier hold wording. Read the full archive and reconcile rules across those briefs and the structured data near the file end. Draft threads, case-study narrative, and decoy section headings are not authoritative.

Fix the Node sources and run:

`node /app/audit-extractor/src/cli.js extract --input <path> --outdir <dir>`

Do not hand-copy files into `/app/output`. Graders always pass `--input /app/data/audit_archive.md` and `--outdir /app/output`. Leave `/tests/` alone.

## CLI requirements

- Subcommand must be `extract`.
- Both `--input` and `--outdir` are required.
- Missing either flag: write an error message to **stderr** that includes the word `missing` (e.g. `missing --input or --outdir`) and exit with code **1**.
- Identical input must produce byte-identical `transactions.json` on repeated runs.

## Output files (write exactly these four under `--outdir`)

| File | Format |
|------|--------|
| `transactions.json` | JSON |
| `transactions.csv` | CSV |
| `exceptions.json` | JSON |
| `reconciliation_report.jsonl` | JSONL (one JSON object per line) |

## `transactions.json`

Top-level envelope:

```json
{ "items": [ /* transaction rows */ ] }
```

Each row in `items`:

| Field | Type | Rules |
|-------|------|-------|
| `transaction_id` | string | `TXN-…` identifier |
| `owner` | string | Reconciled owner |
| `status` | string | Lowercase: `pending`, `approved`, `rejected`, or `reversed` |
| `effective_date` | string | `YYYY-MM-DD` |
| `amount_usd` | number | From ledger; two decimal places in CSV |
| `exception_reason` | string or `null` | Semicolon-joined flag codes in **lexical order**, or `null` when no flag applies (see below) |

Sort `items` by `transaction_id` ascending.

## `transactions.csv`

Header row (exact column order):

`transaction_id,owner,status,effective_date,amount_usd,exception_reason`

- Same rows as `transactions.json` in the **same order**.
- When `exception_reason` is `null`, leave that CSV cell **empty** (do not write the word `null`).
- `amount_usd` must show two decimal places (e.g. `4620.26`).

## `exceptions.json`

```json
{ "items": [ /* flagged rows only */ ] }
```

- Same row shape as `transactions.json`.
- Include **only** rows where `exception_reason` is non-null.
- Sort `items` by `transaction_id` ascending.

## `reconciliation_report.jsonl`

One JSON object per line. Sort lines by `notice_id` ascending. Each object records one winning correction notice:

| Field | Type |
|-------|------|
| `notice_id` | string |
| `transaction_id` | string |
| `field` | string |
| `previous_value` | string |
| `new_value` | string |
| `effective` | string (`YYYY-MM-DD`) |

`previous_value` is the field value **immediately before** that correction applies (after ledger load, meeting amendments, and compliance mail merges).

## Exception flag codes

`exception_reason` uses these exact lowercase codes (join multiple with `;` in lexical order):

| Code | Set when (rules in archive) |
|------|-----------------------------|
| `over_limit` | `amount_usd` strictly exceeds 10000 (Brief 07) |
| `compliance_hold` | Final status is `rejected`, a qualifying `compliance@` email exists with a `sent:` line; sent-date comparison per Brief 09 (Brief 07–09) |
| `policy_waiver` | Final status is `approved`, `amount_usd` > 10000, and an authoritative Policy Exception has `approved_by: compliance` (Brief 08) |
| `retroactive_review` | Final status is `reversed`, `amount_usd` > 5000, and a winning correction notice changed `status` (Brief 08) |

When no code applies, set `exception_reason` to `null`.

## Reconciliation semantics

Ledger sourcing, mail timing, correction precedence, overlay order, and the detailed conditions for each flag above are defined in Investigation Briefs 01–09 of `/app/data/audit_archive.md`. Brief 09 supersedes earlier hold-timing wording where they conflict. Read those briefs to implement merge logic; this prompt names the output shapes and flag code strings graders check.
