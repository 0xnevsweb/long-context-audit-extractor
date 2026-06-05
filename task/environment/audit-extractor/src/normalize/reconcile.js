const { sortByTransactionId } = require("../utils/sort");

const STATUS_ORDER = { pending: 0, approved: 1, rejected: 2, reversed: 3 };

function reconcileTransactions(parsed) {
  const byId = new Map();
  for (const row of parsed.ledger) {
    byId.set(row.transaction_id, { ...row });
  }

  for (const meeting of parsed.meetings) {
    const target = byId.get(meeting.transaction_id);
    if (target) {
      target.owner = meeting.owner;
    }
  }

  for (const email of parsed.emails) {
    const target = byId.get(email.transaction_id);
    if (target) {
      target.status = email.status;
    }
  }

  const report = [];
  for (const notice of parsed.corrections) {
    const target = byId.get(notice.transaction_id);
    if (!target) {
      continue;
    }
    if (notice.field === "owner") {
      target.owner = notice.value;
    } else if (notice.field === "status") {
      target.status = notice.value;
    } else if (notice.field === "date") {
      target.date = notice.value;
    }
    report.push({
      notice_id: notice.notice_id,
      transaction_id: notice.transaction_id,
      field: notice.field,
      previous_value: "",
      new_value: notice.value,
      effective: notice.effective,
    });
  }

  const items = sortByTransactionId(
    [...byId.values()].map((row) => ({
      transaction_id: row.transaction_id,
      owner: row.owner,
      status: String(row.status).toLowerCase(),
      effective_date: row.date,
      amount_usd: Number(row.amount),
      exception_reason: null,
    })),
  );

  return { items, report };
}

module.exports = { reconcileTransactions, STATUS_ORDER };
