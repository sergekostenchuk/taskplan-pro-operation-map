import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const cli = path.join(root, "bin", "taskplan-operation-map.js");
const graph = path.join(root, "examples", "self-hosted", "OPERATION-MAP.json");
const concept = path.join(root, "examples", "self-hosted", "CONCEPT.md");

test("self-hosted example validates and builds from published sources", () => {
  const output = mkdtempSync(path.join(tmpdir(), "operation-map-example-"));
  try {
    const validation = spawnSync(process.execPath, [cli, "validate", "--graph", graph, "--concept", concept], {
      cwd: root,
      encoding: "utf8",
    });
    assert.equal(validation.status, 0, validation.stderr || validation.stdout);
    assert.match(validation.stdout, /"ready": true/);

    const build = spawnSync(process.execPath, [cli, "finalize", "--graph", graph, "--concept", concept, "--output-dir", output], {
      cwd: root,
      encoding: "utf8",
    });
    assert.equal(build.status, 0, build.stderr || build.stdout);

    const audit = JSON.parse(readFileSync(path.join(output, "OPERATION-MAP-AUDIT.json"), "utf8"));
    const manifest = JSON.parse(readFileSync(path.join(output, "OPERATION-MAP-BUILD.json"), "utf8"));
    assert.equal(audit.ready, true);
    assert.equal(audit.graph_id, "taskplan-pro-operation-map-self-hosted");
    assert.equal(manifest.checks.graph_readiness, "passed");
    assert.equal(manifest.checks.browser_smoke, "not_run");
  } finally {
    rmSync(output, { recursive: true, force: true });
  }
});
