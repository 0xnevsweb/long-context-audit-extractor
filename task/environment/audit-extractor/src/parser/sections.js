const { parseLedger } = require("./ledger");
const { parseMeetings } = require("./meetings");
const { parseEmails } = require("./emails");
const { parseCorrections } = require("./corrections");
const { parsePolicyExceptions } = require("./policy");

function parseArchive(markdown) {
  return {
    ledger: parseLedger(markdown),
    meetings: parseMeetings(markdown),
    emails: parseEmails(markdown),
    corrections: parseCorrections(markdown),
    policyExceptions: parsePolicyExceptions(markdown),
  };
}

module.exports = { parseArchive };
