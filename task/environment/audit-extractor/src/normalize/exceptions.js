function buildExceptions(items) {
  return items.filter((row) => row.exception_reason);
}

module.exports = { buildExceptions };
