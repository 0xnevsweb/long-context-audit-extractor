#!/bin/bash
set -euo pipefail

cd /app/audit-extractor

cat <<'EOF' > src/parser/sections.js
const { parseLedger } = require("./ledger");
const { parseMeetings } = require("./meetings");
const { parseEmails } = require("./emails");
const { parseCorrections } = require("./corrections");
const { parsePolicyExceptions } = require("./policy");

function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function findHeadingIndex(markdown, headingLine) {
  const re = new RegExp(`^${escapeRegExp(headingLine)}$`, "m");
  const match = re.exec(markdown);
  return match ? match.index : -1;
}

function sliceSection(markdown, startHeading, endHeading) {
  const start = findHeadingIndex(markdown, startHeading);
  if (start < 0) {
    return "";
  }
  const afterStart = markdown.slice(start);
  if (!endHeading) {
    return afterStart;
  }
  const endRel = findHeadingIndex(afterStart, endHeading);
  if (endRel > 0) {
    return afterStart.slice(0, endRel);
  }
  return afterStart;
}

function parseArchive(markdown) {
  const emailSlice = sliceSection(markdown, "## Email Excerpts", "## Policy Exceptions");
  const policySlice = sliceSection(markdown, "## Policy Exceptions", "## Correction Notices");
  const correctionsSlice = sliceSection(markdown, "## Correction Notices", "## Transaction Ledger");
  const ledgerSlice = sliceSection(markdown, "## Transaction Ledger", null);

  return {
    ledger: parseLedger(ledgerSlice),
    meetings: parseMeetings(markdown),
    emails: parseEmails(emailSlice),
    corrections: parseCorrections(correctionsSlice),
    policyExceptions: parsePolicyExceptions(policySlice),
  };
}

module.exports = { parseArchive, sliceSection, findHeadingIndex };
EOF

cat <<'EOF' > src/parser/ledger.js
function ledgerSlice(markdown) {
  const normalized = markdown.replace(/\r\n/g, "\n");
  const match = normalized.match(/^## Transaction Ledger\s*$/m);
  if (!match) {
    return "";
  }
  const start = match.index;
  const rest = normalized.slice(start + match[0].length);
  const endMatch = rest.match(/^## /m);
  const end = start + match[0].length + (endMatch ? endMatch.index : rest.length);
  return normalized.slice(start, end);
}

function parseLedger(markdown) {
  const section = ledgerSlice(markdown);
  if (!section) {
    return [];
  }
  const byId = new Map();
  for (const block of section.split("\n### ").slice(1)) {
    const lines = block.split("\n");
    const transactionId = lines[0].trim();
    if (!transactionId.startsWith("TXN-")) {
      continue;
    }
    if (/^provisional:\s*true\s*$/im.test(block)) {
      continue;
    }
    const row = { transaction_id: transactionId };
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("amount:")) {
        row.amount = Number(trimmed.split(":")[1].trim());
      } else if (trimmed.startsWith("owner:")) {
        row.owner = trimmed.split(":")[1].trim();
      } else if (trimmed.startsWith("status:")) {
        row.status = trimmed.split(":")[1].trim();
      } else if (trimmed.startsWith("date:")) {
        row.date = trimmed.split(":")[1].trim();
      }
    }
    byId.set(transactionId, row);
  }
  return [...byId.values()];
}

module.exports = { parseLedger };
EOF

cat <<'EOF' > src/parser/meetings.js
function parseMeetings(markdown) {
  const normalized = markdown.replace(/\r\n/g, "\n");
  const meetings = [];
  const re = /^#### Amendment for (TXN-[0-9a-f-]+)\s*$/gim;
  let match;
  while ((match = re.exec(normalized)) !== null) {
    const block = normalized.slice(match.index, match.index + 500);
    const ownerMatch = block.match(/^owner:\s*(.+)$/im);
    const signedMatch = block.match(/^signed:\s*(.+)$/im);
    const effectiveMatch = block.match(/^effective:\s*(\d{4}-\d{2}-\d{2})\s*$/im);
    meetings.push({
      transaction_id: match[1],
      owner: ownerMatch ? ownerMatch[1].trim() : "",
      signed: signedMatch ? signedMatch[1].trim().toLowerCase() === "true" : false,
      effective: effectiveMatch ? effectiveMatch[1] : null,
    });
  }
  return meetings;
}

module.exports = { parseMeetings };
EOF

cat <<'EOF' > src/parser/emails.js
function parseEmails(markdown) {
  const normalized = markdown.replace(/\r\n/g, "\n");
  const start = normalized.indexOf("## Email Excerpts");
  const end = normalized.indexOf("## Policy Exceptions");
  const slice =
    start >= 0 && end > start ? normalized.slice(start, end) : normalized;
  const emails = [];
  for (const block of slice.split("\n\n")) {
    const fromMatch = block.match(/^From:\s*(.+)$/im);
    const subjectMatch = block.match(/^Subject:\s*Re:\s*(TXN-[0-9a-f-]+)/im);
    const statusMatch = block.match(/^status:\s*(\w+)/im);
    const sentMatch = block.match(/^sent:\s*(\d{4}-\d{2}-\d{2})\s*$/im);
    if (!fromMatch || !subjectMatch || !statusMatch) {
      continue;
    }
    emails.push({
      from_addr: fromMatch[1].trim(),
      transaction_id: subjectMatch[1],
      status: statusMatch[1].trim().toLowerCase(),
      sent: sentMatch ? sentMatch[1] : null,
    });
  }
  return emails;
}

module.exports = { parseEmails };
EOF

cat <<'EOF' > src/parser/policy.js
function parsePolicyExceptions(markdown) {
  const normalized = markdown.replace(/\r\n/g, "\n");
  const ids = new Set();
  for (const block of normalized.split("### Policy Exception")) {
    const txnMatch = block.match(/^transaction:\s*(TXN-[0-9a-f-]+)\s*$/im);
    const apprMatch = block.match(/^approved_by:\s*(\S+)\s*$/im);
    if (txnMatch && apprMatch && apprMatch[1].trim().toLowerCase() === "compliance") {
      ids.add(txnMatch[1]);
    }
  }
  return ids;
}

module.exports = { parsePolicyExceptions };
EOF

cat <<'EOF' > src/parser/corrections.js
function parseCorrections(markdown) {
  const normalized = markdown.replace(/\r\n/g, "\n");
  const notices = [];
  for (const block of normalized.split(/^### /m).slice(1)) {
    const lines = block.split("\n");
    const noticeId = lines[0].trim();
    if (!noticeId.startsWith("CORR-")) {
      continue;
    }
    const entry = { notice_id: noticeId };
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("targets:")) {
        entry.transaction_id = trimmed.split(":")[1].trim();
      } else if (trimmed.startsWith("field:")) {
        entry.field = trimmed.split(":")[1].trim();
      } else if (trimmed.startsWith("value:")) {
        entry.value = trimmed.split(":")[1].trim();
      } else if (trimmed.startsWith("effective:")) {
        entry.effective = trimmed.split(":")[1].trim();
      }
    }
    notices.push(entry);
  }
  return notices;
}

module.exports = { parseCorrections };
EOF

cat <<'EOF' > src/normalize/reconcile.js
const { sortByTransactionId } = require("../utils/sort");

const STATUS_ORDER = { pending: 0, approved: 1, rejected: 2, reversed: 3 };

function reconcileTransactions(parsed) {
  const byId = new Map();
  for (const row of parsed.ledger) {
    byId.set(row.transaction_id, { ...row });
  }

  for (const meeting of parsed.meetings) {
    const target = byId.get(meeting.transaction_id);
    if (!target || !meeting.signed) {
      continue;
    }
    if (meeting.effective && meeting.effective < target.date) {
      continue;
    }
    target.owner = meeting.owner;
  }

  for (const email of parsed.emails) {
    const target = byId.get(email.transaction_id);
    if (!target) {
      continue;
    }
    if (!email.from_addr.toLowerCase().includes("compliance@")) {
      continue;
    }
    if (email.sent && email.sent < target.date) {
      continue;
    }
    const cur = String(target.status).toLowerCase();
    const next = email.status.toLowerCase();
    if ((STATUS_ORDER[next] ?? -1) > (STATUS_ORDER[cur] ?? -1)) {
      target.status = next;
    }
  }

  const preCorrectionDates = new Map(
    [...byId.entries()].map(([tid, row]) => [tid, row.date]),
  );

  const report = [];
  const corrByTxn = new Map();
  for (const notice of parsed.corrections) {
    if (!corrByTxn.has(notice.transaction_id)) {
      corrByTxn.set(notice.transaction_id, []);
    }
    corrByTxn.get(notice.transaction_id).push(notice);
  }

  const corrEffDate = new Map();
  const statusCorrected = new Set();
  for (const [tid, notices] of corrByTxn.entries()) {
    const target = byId.get(tid);
    if (!target) {
      continue;
    }
    const byField = new Map();
    for (const notice of notices) {
      if (!byField.has(notice.field)) {
        byField.set(notice.field, []);
      }
      byField.get(notice.field).push(notice);
    }
    const effs = [];
    for (const [field, group] of byField.entries()) {
      const winner = group.reduce((a, b) => (a.effective > b.effective ? a : b));
      let prev;
      if (field === "date") {
        prev = target.date;
      } else if (field === "owner") {
        prev = target.owner;
      } else {
        prev = String(target.status).toLowerCase();
      }
      const newVal = winner.value;
      if (field === "owner") {
        target.owner = newVal;
      } else if (field === "status") {
        target.status = newVal;
        statusCorrected.add(tid);
        effs.push(winner.effective);
      } else if (field === "date") {
        target.date = newVal;
        effs.push(winner.effective);
      }
      report.push({
        notice_id: winner.notice_id,
        transaction_id: tid,
        field,
        previous_value: String(prev),
        new_value: String(newVal),
        effective: winner.effective,
      });
    }
    if (effs.length > 0) {
      corrEffDate.set(tid, effs.reduce((a, b) => (a > b ? a : b)));
    }
  }

  report.sort((a, b) => (a.notice_id < b.notice_id ? -1 : a.notice_id > b.notice_id ? 1 : 0));

  const items = sortByTransactionId(
    [...byId.entries()].map(([tid, row]) => {
      const amount = Number(row.amount);
      const status = String(row.status).toLowerCase();
      const ledgerDate = row.date;
      const reasons = [];
      if (amount > 10000) {
        reasons.push("over_limit");
      }
      const holdCompareDate = preCorrectionDates.get(tid) ?? ledgerDate;
      if (
        status === "rejected" &&
        parsed.emails.some(
          (em) =>
            em.transaction_id === tid &&
            em.from_addr.toLowerCase().includes("compliance@") &&
            em.sent &&
            em.sent >= holdCompareDate,
        )
      ) {
        reasons.push("compliance_hold");
      }
      if (
        status === "approved" &&
        amount > 10000 &&
        parsed.policyExceptions.has(tid)
      ) {
        reasons.push("policy_waiver");
      }
      if (status === "reversed" && amount > 5000 && statusCorrected.has(tid)) {
        reasons.push("retroactive_review");
      }
      reasons.sort();
      return {
        transaction_id: tid,
        owner: row.owner,
        status,
        effective_date: corrEffDate.get(tid) ?? ledgerDate,
        amount_usd: Math.round(amount * 100) / 100,
        exception_reason: reasons.length > 0 ? reasons.join(";") : null,
      };
    }),
  );

  return { items, report };
}

module.exports = { reconcileTransactions, STATUS_ORDER };
EOF

cat <<'EOF' > src/normalize/exceptions.js
function buildExceptions(items) {
  return items.filter((row) => row.exception_reason !== null);
}

module.exports = { buildExceptions };
EOF

cat <<'EOF' > src/output/jsonWriter.js
const fs = require("node:fs");

function writeTransactionsJson(filePath, items) {
  fs.writeFileSync(filePath, `${JSON.stringify({ items }, null, 2)}\n`);
}

function writeExceptionsJson(filePath, items) {
  fs.writeFileSync(filePath, `${JSON.stringify({ items }, null, 2)}\n`);
}

module.exports = { writeTransactionsJson, writeExceptionsJson };
EOF

cat <<'EOF' > src/output/csvWriter.js
const fs = require("node:fs");

function writeTransactionsCsv(filePath, items) {
  const header = "transaction_id,owner,status,effective_date,amount_usd,exception_reason";
  const lines = items.map((row) => {
    const exc = row.exception_reason ?? "";
    const amount = row.amount_usd.toFixed(2);
    return `${row.transaction_id},${row.owner},${row.status},${row.effective_date},${amount},${exc}`;
  });
  fs.writeFileSync(filePath, `${[header, ...lines].join("\n")}\n`);
}

module.exports = { writeTransactionsCsv };
EOF

cat <<'EOF' > src/output/reportWriter.js
const fs = require("node:fs");

function writeReconciliationReport(filePath, report) {
  const sorted = [...report].sort((a, b) =>
    a.notice_id < b.notice_id ? -1 : a.notice_id > b.notice_id ? 1 : 0,
  );
  const body = sorted.map((row) => JSON.stringify(row)).join("\n");
  fs.writeFileSync(filePath, body ? `${body}\n` : "");
}

module.exports = { writeReconciliationReport };
EOF

mkdir -p /app/output
node src/cli.js extract --input /app/data/audit_archive.md --outdir /app/output
