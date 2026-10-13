// Cheap safety nets that need no browser: the JS only references element ids that exist in the
// HTML, and API-provided text is never inserted with innerHTML.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync("frontend/index.html", "utf8");
const app = readFileSync("frontend/js/app.js", "utf8");

test("every $('id') used by app.js exists in index.html", () => {
  const used = [...app.matchAll(/\$\("([\w-]+)"\)/g)].map((m) => m[1]);
  assert.ok(used.length > 20);
  const missing = [...new Set(used)].filter((id) => !html.includes(`id="${id}"`));
  assert.deepEqual(missing, []);
});

test("innerHTML is only used for our own constant SVG icons", () => {
  const uses = app.split("\n").filter((line) => line.includes("innerHTML") && !line.trim().startsWith("//"));
  assert.equal(uses.length, 2);
  assert.ok(uses.every((line) => line.includes("iconSvg(")));
});

test("no inline scripts, inline styles or external assets (strict CSP)", () => {
  assert.ok(!/<script(?![^>]*\bsrc=)/i.test(html));
  assert.ok(!/\sstyle=/i.test(html));
  assert.ok(!/(src|href)="https?:\/\/(?!open-meteo\.com|creativecommons\.org)/i.test(html));
});

test("images/controls have accessible names and the page declares a language", () => {
  assert.match(html, /<html lang="en">/);
  assert.match(html, /<label for="search-input"/);
  assert.match(html, /role="status"/);
});
