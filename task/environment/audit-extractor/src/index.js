const fs = require("node:fs");
const path = require("node:path");
const { parseArchive } = require("./parser/sections");
const { reconcileTransactions } = require("./normalize/reconcile");
const { buildExceptions } = require("./normalize/exceptions");
const { writeTransactionsJson, writeExceptionsJson } = require("./output/jsonWriter");
const { writeTransactionsCsv } = require("./output/csvWriter");
const { writeReconciliationReport } = require("./output/reportWriter");
const { validateOutputs } = require("./schema/validate");

async function runExtract(inputPath, outputDir) {
  const markdown = fs.readFileSync(inputPath, "utf8");
  const parsed = parseArchive(markdown);
  const { items, report } = reconcileTransactions(parsed);
  const exceptions = buildExceptions(items);

  fs.mkdirSync(outputDir, { recursive: true });
  writeTransactionsJson(path.join(outputDir, "transactions.json"), items);
  writeTransactionsCsv(path.join(outputDir, "transactions.csv"), items);
  writeExceptionsJson(path.join(outputDir, "exceptions.json"), exceptions);
  writeReconciliationReport(path.join(outputDir, "reconciliation_report.jsonl"), report);
  validateOutputs(items, exceptions, report);
}

module.exports = { runExtract };
