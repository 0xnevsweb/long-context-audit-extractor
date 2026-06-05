const fs = require("node:fs");

function writeReconciliationReport(filePath, report) {
  const body = report.map((row) => JSON.stringify(row)).join("\n");
  fs.writeFileSync(filePath, body ? `${body}\n` : "");
}

module.exports = { writeReconciliationReport };
