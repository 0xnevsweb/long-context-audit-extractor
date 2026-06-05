const fs = require("node:fs");

function writeTransactionsJson(filePath, items) {
  fs.writeFileSync(filePath, JSON.stringify({ transactions: items }, null, 2));
}

function writeExceptionsJson(filePath, items) {
  fs.writeFileSync(filePath, JSON.stringify({ exceptions: items }, null, 2));
}

module.exports = { writeTransactionsJson, writeExceptionsJson };
