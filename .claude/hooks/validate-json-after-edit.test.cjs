const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const hook = path.join(__dirname, "validate-json-after-edit.cjs");

function invoke(filePath, cwd) {
  return spawnSync(process.execPath, [hook], {
    cwd,
    encoding: "utf8",
    input: JSON.stringify({
      cwd,
      tool_name: "Write",
      tool_input: { file_path: filePath },
    }),
  });
}

test("accepts valid JSON edited inside the repository", (t) => {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), "opsbridge-hook-"));
  t.after(() => fs.rmSync(cwd, { recursive: true, force: true }));
  const file = path.join(cwd, "config.json");
  fs.writeFileSync(file, '{"ok":true}');

  const result = invoke(file, cwd);
  assert.equal(result.status, 0);
  assert.equal(result.stdout, "");
});

test("reports invalid JSON with machine-readable hook feedback", (t) => {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), "opsbridge-hook-"));
  t.after(() => fs.rmSync(cwd, { recursive: true, force: true }));
  const file = path.join(cwd, "config.json");
  fs.writeFileSync(file, '{"ok":');

  const result = invoke(file, cwd);
  const feedback = JSON.parse(result.stdout);
  assert.equal(result.status, 0);
  assert.equal(feedback.decision, "block");
  assert.match(feedback.reason, /JSON validation failed/);
});

test("ignores non-JSON edits", (t) => {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), "opsbridge-hook-"));
  t.after(() => fs.rmSync(cwd, { recursive: true, force: true }));

  const result = invoke(path.join(cwd, "notes.md"), cwd);
  assert.equal(result.status, 0);
  assert.equal(result.stdout, "");
});

test("ignores files outside the repository root", (t) => {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), "opsbridge-hook-root-"));
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), "opsbridge-hook-outside-"));
  t.after(() => fs.rmSync(cwd, { recursive: true, force: true }));
  t.after(() => fs.rmSync(outside, { recursive: true, force: true }));
  const file = path.join(outside, "secrets.json");
  fs.writeFileSync(file, "not json");

  const result = invoke(file, cwd);
  assert.equal(result.status, 0);
  assert.equal(result.stdout, "");
});
