const fs = require("node:fs");
const path = require("node:path");

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);

  let event;
  try {
    event = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    return;
  }

  const candidate = event?.tool_input?.file_path ?? event?.tool_response?.filePath;
  if (typeof candidate !== "string" || path.extname(candidate).toLowerCase() !== ".json") return;

  const repoRoot = path.resolve(event.cwd ?? process.cwd());
  const target = path.resolve(candidate);
  const relative = path.relative(repoRoot, target);
  if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) return;

  try {
    JSON.parse(fs.readFileSync(target, "utf8"));
  } catch (error) {
    const reason = `JSON validation failed for ${relative}: ${error.message}. Fix the file before continuing.`;
    process.stdout.write(JSON.stringify({ decision: "block", reason }));
  }
}

main().catch(() => process.exit(0));
