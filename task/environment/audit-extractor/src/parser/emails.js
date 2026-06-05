function parseEmails(markdown) {
  const start = markdown.indexOf("## Email Excerpts");
  const end = markdown.indexOf("## Policy Exceptions");
  const slice =
    start >= 0 && end > start ? markdown.slice(start, end) : markdown;
  const emails = [];
  const blocks = slice.split(/\n\n+/);
  for (const block of blocks) {
    const fromMatch = block.match(/^From:\s*(.+)$/im);
    const subjectMatch = block.match(/^Subject:\s*Re:\s*(TXN-[0-9a-f-]+)/im);
    const statusMatch = block.match(/^status:\s*(\w+)/im);
    if (!fromMatch || !subjectMatch || !statusMatch) {
      continue;
    }
    emails.push({
      from_addr: fromMatch[1].trim(),
      transaction_id: subjectMatch[1],
      status: statusMatch[1].trim().toLowerCase(),
    });
  }
  return emails;
}

module.exports = { parseEmails };
