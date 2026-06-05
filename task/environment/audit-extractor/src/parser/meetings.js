function parseMeetings(markdown) {
  const meetings = [];
  const re = /^#### Amendment for (TXN-[0-9a-f-]+)\s*$/gim;
  let match;
  while ((match = re.exec(markdown)) !== null) {
    const block = markdown.slice(match.index, match.index + 400);
    const ownerMatch = block.match(/^owner:\s*(.+)$/im);
    const signedMatch = block.match(/^signed:\s*(.+)$/im);
    meetings.push({
      transaction_id: match[1],
      owner: ownerMatch ? ownerMatch[1].trim() : "",
      signed: signedMatch ? signedMatch[1].trim().toLowerCase() === "true" : false,
    });
  }
  return meetings;
}

module.exports = { parseMeetings };
