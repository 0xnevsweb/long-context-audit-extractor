# Audit Extractor

Node CLI under `src/` with subcommand `extract`. Modules under `src/parser` read the markdown input; `src/normalize` applies reconciliation policy from the archive; `src/output` writes JSON, CSV, and JSONL to a caller-provided directory. Policy rules are distributed across Investigation Briefs 01–08 in the archive.