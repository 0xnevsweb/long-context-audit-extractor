const fs = require("node:fs");

function writeTransactionsCsv(filePath, items) {
  const header = "transaction_id,owner,status,effective_date,amount_usd";
  const lines = items.map(
    (row) =>
      `${row.transaction_id},${row.owner},${row.status},${row.effective_date},${row.amount_usd}`,
  );
  fs.writeFileSync(filePath, [header, ...lines].join("\n"));
}

module.exports = { writeTransactionsCsv };
