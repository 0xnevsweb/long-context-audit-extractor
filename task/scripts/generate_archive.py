#!/usr/bin/env python3
"""Generate the FY24 audit archive with distributed policy and substantive narrative."""

from __future__ import annotations

import random
import textwrap
from pathlib import Path

RNG = random.Random(20240605)
OUT = Path(__file__).resolve().parents[1] / "environment" / "audit-extractor" / "data" / "audit_archive.md"
SEED = Path(__file__).resolve().parents[1] / "tests" / "seeds" / "audit_archive.md"

POLICY_BLOCKS: list[tuple[str, str]] = [
    (
        "Investigation Brief 01 — Ledger Sourcing",
        textwrap.dedent(
            """
            Finance QA traced rerun drift to parsers that latched onto the wrong ledger
            slice. For extractor output, treat only the markdown section whose heading
            line is exactly `## Transaction Ledger` as authoritative. The archive also
            contains a working-copy ledger and prose that mentions ledger headings; those
            are investigative context only.

            Ignore any ledger block that includes a line `provisional: true` (case
            insensitive). When the same transaction id appears in multiple non-provisional
            ledger blocks, the last such block in file order is the base row for that id.

            Locate section boundaries with regular expressions anchored to whole heading
            lines at line start. Do not locate sections with indexOf or substring search.
            """
        ).strip(),
    ),
    (
        "Investigation Brief 02 — Status Precedence",
        textwrap.dedent(
            """
            Interview notes with the compliance desk confirmed status fights between mail,
            amendments, and corrections. Ledger rows provide the base status (lowercase on
            output). Status precedence from lowest to highest is: pending, approved,
            rejected, reversed. Email excerpts may change status only when the From line
            contains `compliance@` anywhere in the address; ignore all other senders.
            """
        ).strip(),
    ),
    (
        "Investigation Brief 03 — Compliance Mail Timing",
        textwrap.dedent(
            """
            The March mail-room audit explained missing holds: agents applied compliance
            messages without checking dispatch dates. When an excerpt includes
            `sent: YYYY-MM-DD`, apply the status change only if sent is greater than or
            equal to the ledger date for that transaction. When no `sent:` line is present,
            apply the status change if precedence allows. Correction notices always apply
            after ledger rows, meeting amendments, and mail excerpts have been merged.
            """
        ).strip(),
    ),
    (
        "Investigation Brief 04 — Correction Notice Precedence",
        textwrap.dedent(
            """
            The corrections desk ships multiple notices per field. When several notices
            target the same transaction and field, the notice with the lexicographically
            greatest `effective` date wins. For each winning notice, `previous_value` in
            `reconciliation_report.jsonl` is the field value immediately before that notice
            applies (after ledger, amendments, and emails). Owner corrections override
            both ledger owners and signed meeting amendments when applied in this step.
            """
        ).strip(),
    ),
    (
        "Investigation Brief 05 — Meeting Amendments and Owners",
        textwrap.dedent(
            """
            Committee minutes show owner churn from unsigned drafts. Ledger owner is the
            default. Meeting note amendments under `#### Amendment for TXN-<uuid>` replace
            owner when `signed: true` (case insensitive) and, when the amendment includes
            `effective: YYYY-MM-DD`, only if that date is greater than or equal to the
            ledger date for the transaction.
            """
        ).strip(),
    ),
    (
        "Investigation Brief 06 — Effective Dates on Output",
        textwrap.dedent(
            """
            Auditors compared effective_date columns to correction paperwork. Start from the
            ledger `date` field (YYYY-MM-DD on output). When a winning correction notice
            sets field `date` or `status`, use that notice's `effective` date as
            `effective_date` only if that correction modified status or date; otherwise
            keep the ledger date. `amount_usd` is numeric from the ledger with two decimal
            places in CSV and as a JSON number.
            """
        ).strip(),
    ),
    (
        "Investigation Brief 07 — Exception Flags (Part I)",
        textwrap.dedent(
            """
            Exception coding review: `exception_reason` is null unless a code applies. Set
            `over_limit` when `amount_usd` strictly exceeds 10000. Set `compliance_hold`
            when final status is `rejected`, a qualifying `compliance@` email referenced
            that transaction, and that email block includes a `sent:` line. The sent-date
            comparison used for `compliance_hold` is defined in Investigation Brief 09
            (Mid-Year Amendment), not Brief 03. Multiple reasons join with semicolon in
            lexical order of the reason codes.
            """
        ).strip(),
    ),
    (
        "Investigation Brief 08 — Exception Flags (Part II)",
        textwrap.dedent(
            """
            Continued from Brief 07. Set `policy_waiver` when final status is `approved`,
            `amount_usd` > 10000, and a Policy Exception block exists for that transaction
            with `approved_by: compliance` on its own line. Set `retroactive_review` when
            final status is `reversed`, `amount_usd` > 5000, and a winning correction
            notice changed status for that transaction.
            """
        ).strip(),
    ),
]

AMENDMENT_BLOCK = (
    "Investigation Brief 09 — Mid-Year Amendment",
    textwrap.dedent(
        """
        Mid-year QA found compliance holds disappearing after date corrections. This
        amendment supersedes any earlier wording about hold timing. For `compliance_hold`
        only, compare each qualifying email's `sent:` date against the transaction's
        ledger date immediately before correction notices are applied — that is, the date
        in effect after ledger load, meeting amendments, and compliance mail merges, but
        before any correction notice changes `date` or `status`. Brief 03 still governs
        mail-driven status changes; this amendment governs only the hold flag.
        """
    ).strip(),
)

CASE_TOPICS = [
    ("vendor onboarding backlog", "procurement", "Q1 close"),
    ("treasury wire cutoff failures", "treasury", "February recon"),
    ("SOX sampling mismatch", "internal audit", "March walkthrough"),
    ("intercompany netting dispute", "corporate accounting", "April settlement"),
    ("payroll accrual true-up", "HR finance", "May journal"),
    ("FX revaluation lag", "treasury", "June rates"),
    ("capital project capitalization", "fixed assets", "July review"),
    ("lease modification restatement", "technical accounting", "August memo"),
    ("revenue cutoff testing", "external audit", "September fieldwork"),
    ("inventory obsolescence reserve", "operations finance", "October count"),
    ("grant compliance attestation", "compliance", "November certification"),
    ("year-end close checklist drift", "controller", "December freeze"),
]

REVIEWERS = [
    "M. Chen",
    "R. Okonkwo",
    "S. Patel",
    "L. Bergstrom",
    "A. Ndiaye",
    "J. Huang",
    "K. Morales",
    "T. Singh",
    "E. Novak",
    "P. Okafor",
]

FINDINGS = [
    "mailbox ingestion lag",
    "unsigned amendment drift",
    "correction batch ordering",
    "status precedence inversion",
    "owner field churn",
    "effective-date mismatch",
    "hold flag suppression",
    "ledger slice confusion",
    "policy waiver omission",
    "retroactive status conflict",
]

INVESTIGATION_PASSAGES = [
    "Lead reviewer {name} opened working paper {wp} after {unit} reported that {topic} "
    "distorted the {period} reconciliation. The team reconstructed mailbox ordering and "
    "found {finding} affecting at least {count} transaction threads.",
    "Interview #{num} with {unit} counsel captured how {topic} correspondence referenced "
    "amounts near ${amount:,} without matching ledger rows. Investigators preserved the "
    "thread because {finding} can change downstream exception coding.",
    "During {period}, {name} compared two cold extractor runs and documented {finding} "
    "on {topic}. Operations initially attributed the drift to cache state; QA disproved "
    "that hypothesis the following morning.",
    "Site visit #{num} to {unit} exported {count} compliance threads tied to {topic}. "
    "Reviewers noted that {finding} appeared whenever correction batches straddled a "
    "weekend wire cutoff.",
    "Memo {wp} summarizes a panel on {topic} chaired by {name}. Participants debated "
    "whether informal spreadsheets should ever override ledger owners; Brief 05 closes "
    "that debate for the FY24 extractor.",
    "External advisors reviewing {topic} during {period} asked for a machine-readable "
    "trace explaining why rejected rows received hold flags. The archive preserves "
    "narrative chronology even though only structured tail sections are authoritative.",
    "Follow-up #{num} confirmed that {unit} routed {topic} statements through a shared "
    "inbox with {count} delegates. Investigators flagged {finding} as the likely root "
    "cause of inconsistent status columns.",
    "Risk assessment {wp} links {topic} to control gaps in mail ingestion for {unit}. "
    "The assessment explicitly warns against treating alternate ledger headings or "
    "appendix commentary as transaction sources.",
    "Committee packet #{num} chronicles how {topic} escalated after {name} observed "
    "{finding} between two correction batches. Cross-checks against amendment minutes "
    "were required before accepting any owner change.",
    "Working paper {wp} documents a three-way match failure on {topic} where accrual "
    "true-ups near ${amount:,} never received matching compliance responses during "
    "{period}.",
    "Controller staff described {topic} as a secondary driver of {finding} while "
    "rebuilding the {period} close calendar. They emphasized that decoy ledger headings "
    "in draft appendices must be ignored.",
    "Audit technologist {name} replayed FY24 mailbox snapshots and showed how {topic} "
    "threads arrived out of order relative to correction notices, surfacing {finding} on "
    "four high-balance rows.",
    "In {period}, {unit} migrated {topic} workflows to a new ticketing tool. Migration "
    "cutover introduced {finding}, which did not reproduce once ledger sourcing rules "
    "from Brief 01 were applied manually.",
    "Counsel memo {wp} advises retaining full {topic} threads because litigation hold "
    "scope may extend beyond the transactions named in formal notices.",
    "Operations analyst {name} demonstrated that {topic} batches processed after midnight "
    "UTC inherited stale owner fields, a symptom consistent with {finding} rather than "
    "incorrect amount parsing.",
    "Peer review #{num} of {unit} sampling found {count} mislinked emails on {topic}. "
    "None of the mislinked messages originated from compliance addresses, supporting "
    "Brief 02 sender restrictions.",
    "Treasury liaison {name} explained that {topic} related wires were paused during "
    "{period}, delaying compliance responses and amplifying {finding} on rejected rows.",
    "Internal audit follow-up #{num} tracked how {topic} exceptions were closed without "
    "matching policy waiver paperwork, a separate issue from extractor merge ordering.",
    "Data governance {wp} catalogs legacy {unit} folders still containing {topic} "
    "spreadsheets. Those folders are evidentiary only; extractor output must come from "
    "canonical structured sections.",
    "Draft sidebar (non-authoritative): some prototype tooling compared compliance mail "
    "timestamps against post-correction effective dates when flagging holds. Brief 09 "
    "later in this archive supersedes that draft practice for production reconciliation.",
    "Regional lead {name} hosted a readout on {topic} where finance controllers disputed "
    "whether unsigned meeting notes should override ledger owners; investigators cited "
    "Brief 05 during the session.",
    "Quality review #{num} sampled {count} {topic} tickets and found {finding} whenever "
    "provisional ledger rows were not filtered before merge.",
    "Tax counsel flagged {topic} restatement risk during {period} close, unrelated to "
    "extractor precedence but relevant to why the archive retains full correspondence.",
    "Platform engineer {name} noted that {topic} webhook retries duplicated compliance "
    "messages in the investigative export, requiring deduplication by subject and sent "
    "timestamp during human review.",
    "Stakeholder workshop #{num} on {topic} produced conflicting recollections about "
    "which correction notice superseded an earlier owner change; Brief 04 governs that "
    "precedence for automated output.",
    "SOX testing team {wp} linked {finding} on {topic} to a manual override logged at "
    "02:14 local time between two automated correction imports.",
    "Vendor management {name} described {topic} onboarding delays that pushed compliance "
    "responses past ledger dates on several rejected rows during {period}.",
    "Privacy review #{num} redacted personal data from {topic} threads but retained "
    "transaction identifiers needed for reconciliation testing.",
    "Fixed-assets specialist {name} argued that {topic} capitalization memos should not "
    "alter ledger status; investigators agreed while noting those memos still inform "
    "exception coding narratives.",
    "Grant compliance {wp} tied {topic} attestation gaps to {finding} visible only when "
    "hold flags used corrected rather than pre-correction ledger dates.",
]


def _pick_topic() -> tuple[str, str, str]:
    return RNG.choice(CASE_TOPICS)


def investigation_dossier(title: str, topic: str, unit: str, period: str, count: int) -> str:
    lines = [f"## {title}", ""]
    templates = INVESTIGATION_PASSAGES.copy()
    RNG.shuffle(templates)
    for i in range(count):
        template = templates[i % len(templates)]
        para = template.format(
            name=RNG.choice(REVIEWERS),
            topic=topic,
            unit=unit,
            period=period,
            num=RNG.randint(100, 999),
            wp=f"WP-{RNG.randint(10, 99)}{RNG.randint(10, 99)}",
            finding=RNG.choice(FINDINGS),
            count=RNG.randint(3, 24),
            amount=RNG.randint(1800, 48000),
        )
        lines.append(para)
        lines.append("")
    return "\n".join(lines)


def policy_brief(title: str, policy: str, dossier_count: int) -> list[str]:
    topic, unit, period = _pick_topic()
    lines = [f"## {title}", "", policy, ""]
    lines.append(investigation_dossier(f"{title} — supporting chronology", topic, unit, period, dossier_count))
    return lines


def case_study(idx: int, count: int = 14) -> list[str]:
    topic, unit, period = CASE_TOPICS[idx % len(CASE_TOPICS)]
    return [investigation_dossier(f"Case Study {idx + 1:02d} — {topic.title()}", topic, unit, period, count)]


def decoy_email_excerpts() -> list[str]:
    return [
        "## Email Excerpts (archived thread)",
        "",
        "Non-authoritative mailbox export kept for chronology; do not merge these rows.",
        "",
        "From: compliance@corp.internal",
        "Subject: Re: TXN-88519dfd-79ff-5de0-ae59-862ab932bc25",
        "sent: 2020-01-01",
        "status: reversed",
        "",
        "From: compliance@corp.internal",
        "Subject: Re: TXN-51cc9d8a-ea13-56ab-af16-c55e1716132f",
        "sent: 2024-01-01",
        "status: approved",
        "",
    ]


def decoy_policy_exceptions() -> list[str]:
    return [
        "## Policy Exceptions (draft)",
        "",
        "Draft waiver log — not authoritative for extract output.",
        "",
        "### Policy Exception",
        "transaction: TXN-de3b42d7-919c-5839-a490-b039d9c97092",
        "approved_by: compliance",
        "reason: draft waiver (superseded)",
        "",
        "### Policy Exception",
        "transaction: TXN-68b5423c-1abb-59e6-947e-7e56011cec58",
        "approved_by: finance",
        "reason: draft waiver (superseded)",
        "",
    ]


MAIL_CONTEXT_BODIES = [
    "Team — attaching the refreshed sampling grid for {topic}. No transaction ids in this note; "
    "it exists to preserve ordering around compliance threads during {period}.",
    "Please confirm {unit} coverage for the {topic} walkthrough next week. We are not requesting "
    "any ledger changes from this message.",
    "Legal asked us to retain the full {topic} mailbox export even though most messages lack "
    "transaction subjects. Chronology matters for the investigation narrative.",
    "Controller office moved the {period} close checklist because of {topic} staffing gaps. "
    "This email does not reference compliance@ senders or transaction ids.",
    "Internal audit circulated observations on {topic} controls; findings here are contextual "
    "only and must not override Investigation Brief merge rules.",
    "HR finance noted a payroll accrual discussion unrelated to extractor output. Included for "
    "mailbox ordering fidelity during the {topic} review window.",
    "Treasury ops summarized weekend wire coverage impacts on {topic}. No merge fields present.",
    "External counsel requested preservation of {topic} threads from {period} without implying "
    "any status change authority.",
    "Data platform ticket #{num} tracks an ingestion delay that affected {unit} exports. The "
    "delay is explanatory background, not a reconciliation input.",
    "Risk committee excerpt: {topic} exposure in {period} was elevated but no compliance "
    "decisions are recorded in this message.",
]


def contextual_emails(count: int) -> list[str]:
    lines: list[str] = []
    senders = [
        "audit-lead@corp.internal",
        "treasury-ops@corp.internal",
        "controller@corp.internal",
        "legal-notices@corp.internal",
        "hr-payroll@corp.internal",
    ]
    subjects = [
        "FY24 sampling plan draft",
        "wire desk weekend coverage",
        "close calendar revision",
        "retention hold reminder",
        "accrual true-up schedule",
    ]
    for i in range(count):
        topic, unit, period = _pick_topic()
        sender = RNG.choice(senders)
        subject = RNG.choice(subjects)
        body_t = RNG.choice(MAIL_CONTEXT_BODIES)
        body = body_t.format(topic=topic, unit=unit, period=period, num=RNG.randint(1000, 9999))
        lines.extend(
            [
                f"From: {sender}",
                f"Subject: {subject} — coordination {i}",
                "",
                textwrap.fill(body, width=78),
                "",
            ]
        )
    return lines


def structured_tail() -> list[str]:
    return [
        "## Meeting Notes",
        "",
        "Committee minutes include signed amendments affecting owner fields.",
        "",
        "#### Amendment for TXN-cf3bbd14-d495-5867-b6e2-1d1633f87f15",
        "owner: asmith",
        "signed: true",
        "effective: 2024-02-01",
        "",
        "#### Amendment for TXN-a4dc6038-0c06-5338-9a45-fccff83a6194",
        "owner: bwong",
        "signed: false",
        "",
        "#### Amendment for TXN-caf3e53e-08b7-5f87-a4bc-3cc0e10ff87f",
        "owner: evans",
        "signed: true",
        "effective: 2024-11-01",
        "",
        "#### Amendment for TXN-ba9e6ade-67ce-5a61-b097-ab0d34f8e6bb",
        "owner: earlybird",
        "signed: true",
        "effective: 2020-01-01",
        "",
        "## Email Excerpts",
        "",
        "Investigator commentary: only compliance-addressed threads with transaction "
        "subjects in this section affect merge logic; surrounding mail establishes timing context.",
        "",
        *contextual_emails(80),
        "From: compliance@corp.internal",
        "Subject: Re: TXN-f4d0252e-d346-5489-a8f3-ac035ce359c4",
        "sent: 2024-06-15",
        "status: rejected",
        "",
        "From: alice@corp.internal",
        "Subject: Re: TXN-f4d0252e-d346-5489-a8f3-ac035ce359c4",
        "status: approved",
        "",
        *contextual_emails(50),
        "From: compliance@audit.corp",
        "Subject: Re: TXN-de3b42d7-919c-5839-a490-b039d9c97092",
        "status: rejected",
        "",
        "From: compliance@corp.internal",
        "Subject: Re: TXN-de3b42d7-919c-5839-a490-b039d9c97092",
        "sent: 2024-08-15",
        "status: rejected",
        "",
        *contextual_emails(40),
        "From: compliance@corp.internal",
        "Subject: Re: TXN-1b083448-63e3-5527-a20a-edd71416341c",
        "sent: 2024-08-10",
        "status: rejected",
        "",
        "From: compliance@corp.internal",
        "Subject: Re: TXN-e6379197-8911-50c2-b4eb-e0a8edf1eb0f",
        "sent: 2024-09-01",
        "status: reversed",
        "",
        "## Policy Exceptions",
        "",
        "### Policy Exception",
        "transaction: TXN-68b5423c-1abb-59e6-947e-7e56011cec58",
        "approved_by: compliance",
        "reason: executive waiver",
        "",
        "### Policy Exception",
        "transaction: TXN-2adfa85c-206d-5124-9040-bcb05d88d3e0",
        "approved_by: finance",
        "reason: executive waiver",
        "",
        "### Policy Exception",
        "transaction: TXN-c7416874-b91b-5c2d-92de-0098b1224d18",
        "approved_by: compliance",
        "reason: executive waiver",
        "",
        "## Correction Notices",
        "",
        "### CORR-7f2a91bc",
        "targets: TXN-51cc9d8a-ea13-56ab-af16-c55e1716132f",
        "field: status",
        "value: reversed",
        "effective: 2024-05-10",
        "",
        "### CORR-8e3b02cd",
        "targets: TXN-51cc9d8a-ea13-56ab-af16-c55e1716132f",
        "field: status",
        "value: approved",
        "effective: 2024-06-01",
        "",
        "### CORR-9f4c13de",
        "targets: TXN-51cc9d8a-ea13-56ab-af16-c55e1716132f",
        "field: status",
        "value: reversed",
        "effective: 2024-06-15",
        "",
        "### CORR-a05d24ef",
        "targets: TXN-caf3e53e-08b7-5f87-a4bc-3cc0e10ff87f",
        "field: owner",
        "value: dlee",
        "effective: 2024-04-20",
        "",
        "### CORR-b16e35f0",
        "targets: TXN-e6379197-8911-50c2-b4eb-e0a8edf1eb0f",
        "field: date",
        "value: 2024-08-01",
        "effective: 2024-08-01",
        "",
        "### CORR-c27e46a1",
        "targets: TXN-1b083448-63e3-5527-a20a-edd71416341c",
        "field: date",
        "value: 2024-09-01",
        "effective: 2024-09-01",
        "",
        "## Transaction Ledger (working copy)",
        "",
        "### TXN-88519dfd-79ff-5de0-ae59-862ab932bc25",
        "amount: 99999.00",
        "owner: decoy",
        "status: reversed",
        "date: 2020-01-01",
        "",
        "## Transaction Ledger",
        "",
        "### TXN-88519dfd-79ff-5de0-ae59-862ab932bc25",
        "amount: 500.00",
        "owner: jdoe",
        "status: pending",
        "date: 2024-01-01",
        "",
        "### TXN-51cc9d8a-ea13-56ab-af16-c55e1716132f",
        "amount: 7500.00",
        "owner: asmith",
        "status: approved",
        "date: 2024-02-02",
        "",
        "### TXN-cf3bbd14-d495-5867-b6e2-1d1633f87f15",
        "amount: 3246.84",
        "owner: bwong",
        "status: rejected",
        "date: 2024-03-03",
        "",
        "### TXN-ba9e6ade-67ce-5a61-b097-ab0d34f8e6bb",
        "amount: 4620.26",
        "owner: ckim",
        "status: approved",
        "date: 2024-04-04",
        "",
        "### TXN-f4d0252e-d346-5489-a8f3-ac035ce359c4",
        "amount: 5993.68",
        "owner: dlee",
        "status: pending",
        "date: 2024-05-05",
        "",
        "### TXN-a4dc6038-0c06-5338-9a45-fccff83a6194",
        "amount: 7367.10",
        "owner: evans",
        "status: pending",
        "date: 2024-06-06",
        "",
        "### TXN-68b5423c-1abb-59e6-947e-7e56011cec58",
        "amount: 8740.52",
        "owner: frost",
        "status: approved",
        "date: 2024-07-07",
        "",
        "### TXN-1b083448-63e3-5527-a20a-edd71416341c",
        "amount: 10113.94",
        "owner: jdoe",
        "status: rejected",
        "date: 2024-08-08",
        "",
        "### TXN-caf3e53e-08b7-5f87-a4bc-3cc0e10ff87f",
        "amount: 11487.36",
        "owner: asmith",
        "status: approved",
        "date: 2024-09-09",
        "",
        "### TXN-0f577e8c-c09d-517f-8807-b09a17924f9c",
        "amount: 12860.78",
        "owner: bwong",
        "status: pending",
        "date: 2024-10-10",
        "",
        "### TXN-33c930a7-114e-50c1-b790-e26c53e5f025",
        "amount: 14234.20",
        "owner: ckim",
        "status: pending",
        "date: 2024-11-11",
        "",
        "### TXN-de3b42d7-919c-5839-a490-b039d9c97092",
        "amount: 15607.62",
        "owner: dlee",
        "status: approved",
        "date: 2024-12-12",
        "",
        "### TXN-9ed28e5d-b453-5580-bf81-a75bad4f244f",
        "amount: 16981.04",
        "owner: evans",
        "status: rejected",
        "date: 2024-01-13",
        "",
        "### TXN-53e38083-cc01-56a8-be81-f412d80c5f5d",
        "amount: 18354.46",
        "owner: frost",
        "status: approved",
        "date: 2024-02-14",
        "",
        "### TXN-378cf202-0cc9-578e-91ea-d8d008c534e9",
        "amount: 19727.88",
        "owner: jdoe",
        "status: pending",
        "date: 2024-03-15",
        "",
        "### TXN-e6379197-8911-50c2-b4eb-e0a8edf1eb0f",
        "amount: 1601.30",
        "owner: asmith",
        "status: pending",
        "date: 2024-04-16",
        "",
        "### TXN-c4523d54-1ba5-5ec4-bfa5-4488edf1cf7c",
        "amount: 2974.72",
        "owner: bwong",
        "status: approved",
        "date: 2024-05-17",
        "",
        "### TXN-36d4fdbe-3be1-54ab-9023-dda438c2b25a",
        "amount: 4348.14",
        "owner: ckim",
        "status: rejected",
        "date: 2024-06-18",
        "",
        "### TXN-16df04da-aef5-5537-ae87-993fc75b7be3",
        "amount: 5721.56",
        "owner: dlee",
        "status: approved",
        "date: 2024-07-19",
        "",
        "### TXN-8b12c2e5-aa51-56b4-8d88-55960b96f966",
        "amount: 7094.98",
        "owner: evans",
        "status: pending",
        "date: 2024-08-20",
        "",
        "### TXN-2adfa85c-206d-5124-9040-bcb05d88d3e0",
        "amount: 8468.40",
        "owner: frost",
        "status: pending",
        "date: 2024-09-21",
        "",
        "### TXN-6bfa43be-6dd7-5460-9f47-24258c5d400f",
        "amount: 9841.82",
        "owner: jdoe",
        "status: approved",
        "date: 2024-10-22",
        "",
        "### TXN-c7416874-b91b-5c2d-92de-0098b1224d18",
        "amount: 11215.24",
        "owner: asmith",
        "status: rejected",
        "date: 2024-11-23",
        "",
        "### TXN-20cd5f27-165a-55cf-90db-b472725bb03b",
        "amount: 12588.66",
        "owner: bwong",
        "status: approved",
        "date: 2024-12-24",
        "",
        "### TXN-95eb9be1-7793-5e4e-a02e-4603b4047d1a",
        "amount: 13962.08",
        "owner: ckim",
        "status: pending",
        "date: 2024-01-25",
        "",
        "### TXN-08b4472a-f4b7-5455-9f43-e97005d4a594",
        "amount: 15335.50",
        "owner: dlee",
        "status: pending",
        "date: 2024-02-26",
        "",
        "### TXN-6a290cff-b5f2-5992-9a90-1f22dedca980",
        "amount: 16708.92",
        "owner: evans",
        "status: approved",
        "date: 2024-03-27",
        "",
        "### TXN-b9168e33-01d4-5be8-b55f-2d6ae4f5bdc8",
        "amount: 18082.34",
        "owner: frost",
        "status: rejected",
        "date: 2024-04-01",
        "",
        "### TXN-5ec29c5b-5b2d-5a19-88af-ed46090db8d1",
        "amount: 19455.76",
        "owner: jdoe",
        "status: approved",
        "date: 2024-05-02",
        "",
        "### TXN-bb6114bb-5393-5c83-843c-0d9acc971ab9",
        "amount: 1329.18",
        "owner: asmith",
        "status: pending",
        "date: 2024-06-03",
        "",
        "### TXN-7096e296-6315-5a4f-a6b9-907aa2893b8a",
        "amount: 2702.60",
        "owner: bwong",
        "status: pending",
        "date: 2024-07-04",
        "",
        "### TXN-6b005945-fb10-584b-91bf-629e2cfe98a3",
        "amount: 4076.02",
        "owner: ckim",
        "status: approved",
        "date: 2024-08-05",
        "",
        "### TXN-ba9e6ade-67ce-5a61-b097-ab0d34f8e6bb",
        "amount: 4620.26",
        "owner: stale",
        "status: pending",
        "date: 2024-04-04",
        "provisional: true",
        "",
        "### TXN-ba9e6ade-67ce-5a61-b097-ab0d34f8e6bb",
        "amount: 4620.26",
        "owner: finalowner",
        "status: approved",
        "date: 2024-04-04",
        "",
    ]


def build_corpus() -> str:
    parts: list[str] = [
        "# FY24 Internal Audit Archive",
        "",
        "Mixed investigation briefs, committee minutes, mail excerpts, policy exceptions, "
        "correction notices, and ledger rows. Extractor policy is distributed across the file.",
        "",
        "## Reconciliation and Exception Policy (FY24 Audit Handbook)",
        "",
        "This index orients readers only. Reconciliation rules appear inside Investigation "
        "Briefs 01–08 and the Mid-Year Amendment in Brief 09. Draft narrative, decoy "
        "sections, and archived threads are not authoritative. Structured source data "
        "appears near the file end under Email Excerpts, Policy Exceptions, Correction "
        "Notices, and the canonical Transaction Ledger heading.",
        "",
        "Brief 09 supersedes earlier hold-timing wording in narrative drafts and partially "
        "defers Brief 07 on compliance_hold date comparison.",
        "",
    ]

    parts.extend(policy_brief(POLICY_BLOCKS[0][0], POLICY_BLOCKS[0][1], 28))
    parts.extend(case_study(0, 28))
    parts.extend(case_study(1, 28))
    parts.extend(decoy_email_excerpts())
    parts.extend(policy_brief(POLICY_BLOCKS[1][0], POLICY_BLOCKS[1][1], 26))
    parts.extend(case_study(2, 26))
    parts.extend(case_study(3, 26))
    parts.extend(policy_brief(POLICY_BLOCKS[2][0], POLICY_BLOCKS[2][1], 26))
    parts.extend(case_study(4, 26))
    parts.extend(case_study(5, 26))
    parts.extend(policy_brief(POLICY_BLOCKS[3][0], POLICY_BLOCKS[3][1], 26))
    parts.extend(case_study(6, 26))
    parts.extend(policy_brief(POLICY_BLOCKS[4][0], POLICY_BLOCKS[4][1], 26))
    parts.extend(case_study(7, 26))
    parts.extend(decoy_policy_exceptions())
    parts.extend(case_study(8, 26))
    parts.extend(policy_brief(POLICY_BLOCKS[5][0], POLICY_BLOCKS[5][1], 26))
    parts.extend(case_study(9, 26))
    parts.extend(policy_brief(POLICY_BLOCKS[6][0], POLICY_BLOCKS[6][1], 26))
    parts.extend(case_study(10, 26))
    parts.extend(case_study(11, 26))
    parts.extend(policy_brief(POLICY_BLOCKS[7][0], POLICY_BLOCKS[7][1], 26))
    parts.extend(case_study(0, 30))
    parts.extend(case_study(3, 30))
    parts.extend(case_study(1, 30))
    parts.extend(case_study(5, 30))
    parts.extend(policy_brief(AMENDMENT_BLOCK[0], AMENDMENT_BLOCK[1], 28))
    parts.extend(case_study(6, 30))
    parts.extend(case_study(8, 30))
    parts.extend(case_study(10, 30))
    parts.extend(structured_tail())

    return "\n".join(parts) + "\n"


def main() -> None:
    corpus = build_corpus()
    OUT.write_text(corpus, encoding="utf-8")
    SEED.write_text(corpus, encoding="utf-8")
    chars = len(corpus)
    lines = [line.strip() for line in corpus.splitlines() if line.strip()]
    unique_ratio = len(set(lines)) / len(lines)
    marker = "## Investigation Brief 09 — Mid-Year Amendment"
    pos_09 = corpus.find(marker)
    print(f"wrote {OUT} ({chars:,} chars, ~{chars // 4:,} tokens)")
    print(f"unique line ratio: {unique_ratio:.3f}")
    print(f"Brief 09 starts at char {pos_09:,} ({100 * pos_09 / chars:.1f}% into file)")


if __name__ == "__main__":
    main()
