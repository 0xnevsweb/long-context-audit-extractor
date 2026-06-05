function parsePolicyExceptions(markdown) {
  const start = markdown.indexOf("## Policy Exceptions");
  const end = markdown.indexOf("## Correction Notices");
  const slice =
    start >= 0 && end > start ? markdown.slice(start, end) : "";
  const ids = new Set();
  const re = /^transaction:\s*(TXN-[0-9a-f-]+)\s*$/gim;
  let match;
  while ((match = re.exec(slice)) !== null) {
    ids.add(match[1]);
  }
  return ids;
}

module.exports = { parsePolicyExceptions };
