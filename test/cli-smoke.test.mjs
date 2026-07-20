import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const cli = path.join(root, "bin", "taskplan-operation-map.js");
const graph = path.join(root, "skill", "evals", "fixtures", "valid-operation-map.json");
const concept = path.join(root, "skill", "evals", "fixtures", "accepted-concept.md");

test("CLI exposes the operation-map commands", () => {
  const result = spawnSync(process.execPath, [cli, "--help"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /validate,finalize,review/);
});

test("CLI validates the bundled fixture and writes a report", () => {
  const output = mkdtempSync(path.join(tmpdir(), "taskplan-operation-map-"));
  const report = path.join(output, "audit.json");
  const result = spawnSync(
    process.execPath,
    [cli, "validate", "--graph", graph, "--concept", concept, "--report", report],
    { encoding: "utf8" },
  );
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  const audit = JSON.parse(readFileSync(report, "utf8"));
  assert.equal(audit.ready, true);
  assert.deepEqual(audit.errors, []);
});
