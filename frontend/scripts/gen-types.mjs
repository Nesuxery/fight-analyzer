// Generate src/contracts/generated.ts from the backend JSON Schema and
// src/contracts/overlayStyle.ts from shared/overlay-style.json (the overlay
// colours and effect timings the MP4 export uses too).
//   npm run gen:types      write the files
//   npm run check:types    exit 1 if a file is out of date
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const here = path.dirname(fileURLToPath(import.meta.url));
const schemaFile = "shared/schemas/fight-analyzer.v1.schema.json";
const schemaPath = path.resolve(here, "../..", schemaFile);
const outPath = path.resolve(here, "../src/contracts/generated.ts");
const styleFile = "shared/overlay-style.json";
const stylePath = path.resolve(here, "../..", styleFile);
const styleOutPath = path.resolve(here, "../src/contracts/overlayStyle.ts");

const schema = JSON.parse(await readFile(schemaPath, "utf8"));

// json2ts turns every titled schema, and every $ref with sibling keywords
// (description/default), into a separate named type (X1, CheckStatus1, ...).
// Keep titles only on the named $defs and reduce such refs to a bare $ref.
function normalize(node, keepTitle) {
  if (Array.isArray(node)) return node.forEach((n) => normalize(n, false));
  if (node === null || typeof node !== "object") return;
  if ("$ref" in node) {
    for (const key of Object.keys(node)) if (key !== "$ref") delete node[key];
    return;
  }
  if (!keepTitle) delete node.title;
  for (const [key, value] of Object.entries(node)) {
    if (key === "$defs") Object.values(value).forEach((def) => normalize(def, true));
    else if (key !== "enum" && key !== "default") normalize(value, false);
  }
}
normalize(schema, true);

const version = schema["x-schema-version"];
let ts = await compile(schema, "FightAnalyzerContracts", {
  bannerComment: `/* Generated from ${schemaFile} by \`npm run gen:types\`. Do not edit by hand. */`,
  additionalProperties: false,
  unreachableDefinitions: true,
  // Plain arrays instead of 17-element tuple types; lengths are validated server-side.
  ignoreMinAndMaxItems: true,
  style: { printWidth: 100 },
});
ts += `\n/** Contract version this UI was built against. */\nexport const SCHEMA_VERSION = "${version}";\n`;

const style = JSON.parse(await readFile(stylePath, "utf8"));
const styleTs = [
  `/* Generated from ${styleFile} by \`npm run gen:types\`. Do not edit by hand. */`,
  "/** Overlay style shared with the MP4 export (backend/fight_analyzer/export/style.py). */",
  `export const OVERLAY_STYLE = ${JSON.stringify(style, null, 2)} as const;`,
  "",
].join("\n");

const outputs = [[outPath, ts], [styleOutPath, styleTs]];
if (process.argv.includes("--check")) {
  let stale = false;
  for (const [file, content] of outputs) {
    const current = await readFile(file, "utf8").catch(() => "");
    if (current !== content) {
      console.error(`${path.relative(process.cwd(), file)} is out of date; run npm run gen:types`);
      stale = true;
    }
  }
  if (stale) process.exit(1);
  console.log("generated files are up to date");
} else {
  for (const [file, content] of outputs) await writeFile(file, content, "utf8");
  console.log(`wrote generated.ts (schema ${version}) and overlayStyle.ts`);
}
