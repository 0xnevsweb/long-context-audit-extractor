# Audit Extractor

Node CLI under `src/` with subcommand `extract`. Modules under `src/parser` read the markdown input; `src/normalize` applies reconciliation policy from the archive; `src/output` writes JSON, CSV, and JSONL to a caller-provided directory.

Output file names and row shapes: `docs/extractor-output-contract.md`. Reconciliation policy is distributed across Investigation Briefs 01–09 in the input archive.
