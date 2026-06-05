#!/usr/bin/env node
const { runExtract } = require("./index");

function parseArgs(argv) {
  const args = { input: null, outdir: null };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--input" && argv[i + 1]) {
      args.input = argv[++i];
    } else if (argv[i] === "--outdir" && argv[i + 1]) {
      args.outdir = argv[++i];
    }
  }
  return args;
}

async function main() {
  const [command, ...rest] = process.argv.slice(2);
  if (command !== "extract") {
    process.stderr.write("usage: node src/cli.js extract --input <path> --outdir <dir>\n");
    process.exit(1);
  }
  const opts = parseArgs(rest);
  if (!opts.input || !opts.outdir) {
    process.stderr.write("missing --input or --outdir\n");
    process.exit(1);
  }
  try {
    await runExtract(opts.input, opts.outdir);
  } catch (err) {
    process.stderr.write(`${err.message}\n`);
    process.exit(1);
  }
}

main();
