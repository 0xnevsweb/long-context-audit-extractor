function sortByTransactionId(items) {
  return items.sort((a, b) => (a.transaction_id < b.transaction_id ? -1 : 1));
}

module.exports = { sortByTransactionId };
