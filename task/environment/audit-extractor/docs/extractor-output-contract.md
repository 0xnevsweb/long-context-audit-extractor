# Audit Extractor Output Contract

Service root: `/app/audit-extractor`

## CLI

`node /app/audit-extractor/src/cli.js extract --input <markdown-path> --outdir <directory>`

Missing `--input` or `--outdir`: message on stderr, exit code 1.

Reconciliation semantics (ledger sourcing, mail timing, correction precedence, exception flags, overlay order) are defined only in Investigation Briefs 01–09 of the input markdown at `/app/data/audit_archive.md`. Brief 09 supersedes earlier hold-timing wording where they conflict.

Output filenames, field schemas, CSV header order, and CLI requirements are specified in the task `instruction.md` at `/app/instruction.md` during evaluation. This document mirrors those shapes for local reference.

## Artifacts

`extract` writes exactly these files under `--outdir`:

- `transactions.json`
- `transactions.csv`
- `exceptions.json`
- `reconciliation_report.jsonl`

Identical input must produce byte-identical `transactions.json` on repeated runs.

## `transactions.json`

Top-level envelope:

```json
{ "items": [ /* transaction rows */ ] }
```

Each row:

| Field | Type | Notes |
|-------|------|-------|
| `transaction_id` | string | `TXN-…` |
| `owner` | string | |
| `status` | string | lowercase: `pending`, `approved`, `rejected`, `reversed` |
| `effective_date` | string | `YYYY-MM-DD` |
| `amount_usd` | number | two decimal places |
| `exception_reason` | string or null | semicolon-joined flag codes in lexical order, or null |

Sort `items` by `transaction_id` ascending.

## `transactions.csv`

Header (exact order):

`transaction_id,owner,status,effective_date,amount_usd,exception_reason`

Same rows as `transactions.json` in the same order. Empty cell when `exception_reason` is null.

## `exceptions.json`

```json
{ "items": [ /* flagged rows only */ ] }
```

Same row shape as `transactions.json`. Include only rows where `exception_reason` is non-null. Sort by `transaction_id` ascending.

## `reconciliation_report.jsonl`

One JSON object per line, sorted by `notice_id` ascending. Each line records one winning correction notice:

| Field | Type |
|-------|------|
| `notice_id` | string |
| `transaction_id` | string |
| `field` | string |
| `previous_value` | string |
| `new_value` | string |
| `effective` | string |

`previous_value` is the field value immediately before that correction applies.
