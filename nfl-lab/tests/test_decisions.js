const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(require("node:path").join(__dirname, "../assets/decisions.js"), "utf8");
const storage = new Map();
const handlers = {};
const select = {
  dataset: { decision: "S1" },
  value: "",
  options: [
    { value: "", textContent: "Unreviewed" },
    { value: "A", textContent: "A — License a documented odds feed" },
    { value: "B", textContent: "B — Keep nfldata with a disclosure" },
  ],
  addEventListener(name, handler) { handlers[`select:${name}`] = handler; },
};
const rowStatus = {
  dataset: { decisionStatus: "S1" },
  textContent: "awaiting your choice",
  className: "pending",
};
const pageStatus = { textContent: "No review choices saved." };
const exportButton = { addEventListener(name, handler) { handlers[`export:${name}`] = handler; } };
const clearButton = { addEventListener(name, handler) { handlers[`clear:${name}`] = handler; } };
let downloadedBlob = null;
let downloadedAnchor = null;

class FakeBlob {
  constructor(parts, options) { this.parts = parts; this.options = options; downloadedBlob = this; }
}

const document = {
  querySelectorAll(selector) {
    if (selector === "select[data-decision]") return [select];
    if (selector === "[data-decision-status]") return [rowStatus];
    return [];
  },
  getElementById(id) {
    return {
      "decision-status": pageStatus,
      "export-decisions": exportButton,
      "clear-decisions": clearButton,
    }[id] || null;
  },
  createElement(tag) {
    assert.equal(tag, "a");
    downloadedAnchor = {
      click() { this.clicked = true; },
      remove() { this.removed = true; },
    };
    return downloadedAnchor;
  },
  body: { appendChild() {} },
};

const context = {
  document,
  window: {
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, value); },
      removeItem(key) { storage.delete(key); },
    },
  },
  Blob: FakeBlob,
  URL: {
    createObjectURL(blob) { assert.equal(blob, downloadedBlob); return "blob:local-test"; },
    revokeObjectURL(url) { assert.equal(url, "blob:local-test"); },
  },
};

vm.runInNewContext(source, context, { filename: "decisions.js" });

select.value = "A";
handlers["select:change"]();
const saved = JSON.parse(storage.get("korea5.nfl-lines-lab.decisions.v1"));
assert.equal(saved.decisions.S1, "A");
assert.equal(saved.storage, "this browser only");
assert.match(rowStatus.textContent, /selected A.*local only/);
assert.match(pageStatus.textContent, /nothing was sent/);

handlers["export:click"]();
assert.equal(downloadedAnchor.download, "nfl-lines-lab-decisions.json");
assert.equal(downloadedAnchor.clicked, true);
assert.equal(downloadedBlob.options.type, "application/json");
assert.match(downloadedBlob.parts[0], /"S1": "A"/);

handlers["clear:click"]();
assert.equal(select.value, "");
assert.equal(storage.has("korea5.nfl-lines-lab.decisions.v1"), false);
assert.equal(rowStatus.textContent, "awaiting your choice");
assert.match(pageStatus.textContent, /cleared/);

console.log("NFL Lines Lab local decision UI tests passed.");
