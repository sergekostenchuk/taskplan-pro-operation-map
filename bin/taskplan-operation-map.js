#!/usr/bin/env node

"use strict";

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const script = path.resolve(__dirname, "..", "skill", "scripts", "operation_map.py");
const args = [script, ...process.argv.slice(2)];
const candidates = process.platform === "win32" ? ["python", "py"] : ["python3", "python"];

for (const command of candidates) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (!result.error) {
    process.exit(result.status ?? 1);
  }
  if (result.error.code !== "ENOENT") {
    console.error(`Failed to start ${command}: ${result.error.message}`);
    process.exit(1);
  }
}

console.error("TASKPLAN PRO Operation Map requires Python 3.10 or newer in PATH.");
process.exit(127);
