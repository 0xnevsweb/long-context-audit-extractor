const fs = require("node:fs");
const path = require("node:path");

function loadDefaults() {
  const file = path.join(__dirname, "..", "..", "config", "defaults.json");
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

module.exports = { loadDefaults };
