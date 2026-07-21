import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));

test("package declares BSL 1.1 and has no install hooks", () => {
  assert.equal(manifest.license, "BUSL-1.1");
  const license = readFileSync(path.join(root, "LICENSE"), "utf8");
  assert.match(license, /^Business Source License 1\.1$/m);
  assert.match(license, /^Additional Use Grant:/m);
  assert.match(license, /^Change Date: 2030-07-21$/m);
  assert.match(license, /^Change License: GNU General Public License Version 2 or later$/m);
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
