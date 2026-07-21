import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));

test("package has an explicit non-commercial license and no install hooks", () => {
  assert.equal(manifest.license, "SEE LICENSE IN LICENSE");
  for (const hook of ["preinstall", "install", "postinstall", "prepare"] ) {
    assert.equal(manifest.scripts?.[hook], undefined);
  }
});

test("published surface is an allowlist", () => {
  assert.deepEqual(manifest.files, [
    "bin/",
    "skill/",
    "!skill/**/__pycache__/**",
    "!skill/**/*.py[cod]",
    "examples/self-hosted/",
    "!examples/self-hosted/generated/",
    "docs/images/",
    "docs/vendors/",
    "README.md",
    "README.ru.md",
    "LICENSE",
    "SECURITY.md",
    "CHANGELOG.md",
  ]);
});
