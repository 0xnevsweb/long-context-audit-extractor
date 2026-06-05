function validateOutputs(items, exceptions, report) {
  if (!Array.isArray(items) || items.length === 0) {
    throw new Error("no transactions produced");
  }
  if (!Array.isArray(exceptions)) {
    throw new Error("invalid exceptions");
  }
  if (!Array.isArray(report)) {
    throw new Error("invalid report");
  }
}

module.exports = { validateOutputs };
