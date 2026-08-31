#!/usr/bin/env node
"use strict";

const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const appPath = process.argv[2];
if (!appPath) {
  process.stderr.write("usage: operator_ui_stale_request_harness.js <app.js>\n");
  process.exit(2);
}

const EMPTY_ANSWER = "輸入 USB 規格問題後，這裡會顯示有依據的回答。";
const STALE_ANSWER = "STALE_ANSWER_MUST_NOT_RENDER";
const STALE_PAYLOAD = {
  status: "answer",
  answer: STALE_ANSWER,
  source: "fixture",
  scope: "USB_3_X",
  citations: [],
  claims: [],
  boundary_code: "",
};

const ELEMENT_IDS = [
  "devChip", "fixtureChip", "question", "askBtn", "askError", "advancedFold",
  "answerScope", "retrievalMode", "retrievalHint", "allowedScopesField",
  "allowedScopes", "source", "fixtureField", "fixture", "fixtureIgnoreHint",
  "resultPanel", "answerHeading", "statusRow", "explainer", "answerText",
  "sourceKicker", "sourceLine", "sourceMeta", "sourceOpen", "evidenceFold",
  "evidenceSummary", "evidenceDesc", "evidenceCount", "citations",
  "governanceFold", "devModeCopy", "dataSource", "developerCitations",
  "scopeText", "claims", "boundaryBlock", "boundaryCode", "boundaryReason",
];

class El {
  constructor(id, tagName) {
    this.id = id;
    this.tagName = tagName;
    this.children = [];
    this.listeners = Object.create(null);
    this.hidden = false;
    this.disabled = false;
    this.readOnly = false;
    this.placeholder = "";
    this.value = "";
    this.textContent = "";
    this.className = "";
    this.style = {};
    this.scrollHeight = 48;
    this.open = false;
    this.parentNode = null;
    this.href = "";
  }

  get firstChild() {
    return this.children[0] || null;
  }

  addEventListener(type, fn) {
    (this.listeners[type] || (this.listeners[type] = [])).push(fn);
  }

  dispatchEvent(ev) {
    const type = ev && ev.type;
    for (const fn of this.listeners[type] || []) fn(ev);
    return true;
  }

  appendChild(child) {
    if (child.parentNode) child.parentNode.removeChild(child);
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  removeChild(child) {
    this.children = this.children.filter((item) => item !== child);
    child.parentNode = null;
    return child;
  }

  insertBefore(newNode, refNode) {
    if (newNode.parentNode) newNode.parentNode.removeChild(newNode);
    const index = this.children.indexOf(refNode);
    newNode.parentNode = this;
    if (index < 0) this.children.push(newNode);
    else this.children.splice(index, 0, newNode);
    return newNode;
  }

  removeAttribute(name) {
    if (name === "href") this.href = "";
  }

  click() {
    return this.dispatchEvent({ type: "click" });
  }
}

function tick() {
  return new Promise((resolve) => setImmediate(resolve));
}

function boot() {
  const elements = Object.create(null);
  for (const id of ELEMENT_IDS) {
    elements[id] = new El(id, "div");
  }
  elements.question.tagName = "textarea";
  elements.question.value = "USB 3.x Hub Class 的 PORT_POWER feature selector 值是多少？";
  elements.source.value = "fixture";
  elements.fixture.value = "answered";
  elements.answerScope.value = "USB_3_X";
  elements.retrievalMode.value = "single_scope";
  elements.allowedScopes.value = "";
  elements.answerText.textContent = EMPTY_ANSWER;
  elements.answerText.className = "answer is-empty";
  elements.statusRow.textContent = "等待中";
  elements.dataSource.textContent = "waiting";
  elements.fixtureChip.textContent = "範例";
  elements.sourceLine.textContent = "尚無來源";

  const paper = new El("paper", "div");
  paper.appendChild(elements.explainer);
  paper.appendChild(elements.answerText);

  const pending = [];
  const fetchImpl = (url, init) => new Promise((resolve, reject) => {
    const rec = { resolve, reject, aborted: false };
    const signal = init && init.signal;
    if (signal) {
      if (signal.aborted) {
        const err = new Error("Aborted");
        err.name = "AbortError";
        reject(err);
        return;
      }
      signal.addEventListener("abort", () => {
        rec.aborted = true;
        const err = new Error("Aborted");
        err.name = "AbortError";
        reject(err);
      });
    }
    pending.push(rec);
  });

  const context = vm.createContext({
    console,
    AbortController,
    URL,
    setTimeout,
    clearTimeout,
    fetch: fetchImpl,
    window: { location: { origin: "http://127.0.0.1" } },
    document: {
      getElementById: (id) => elements[id] || null,
      createElement: (tag) => new El(null, tag),
    },
  });
  vm.runInContext(fs.readFileSync(appPath, "utf8"), context, { filename: appPath });
  return { elements, pending };
}

async function resolveOldest(pending, payload) {
  const rec = pending.shift();
  if (!rec || rec.aborted) {
    await tick();
    return;
  }
  rec.resolve({
    ok: true,
    json: async () => payload,
  });
  await tick();
  await tick();
}

async function runControl(control, value) {
  const { elements, pending } = boot();
  elements.askBtn.click();
  await tick();
  assert.strictEqual(pending.length, 1, `${control}: fetch was not started`);
  if (control === "source" || control === "fixture" || control === "answerScope" || control === "retrievalMode") {
    elements[control].value = value;
  } else {
    elements[control].value = value;
  }
  elements[control].dispatchEvent({ type: "change" });
  await tick();
  assert.strictEqual(elements.answerText.textContent, EMPTY_ANSWER, `${control}: waiting answer after change`);
  assert.strictEqual(elements.dataSource.textContent, "waiting", `${control}: waiting source after change`);
  await resolveOldest(pending, STALE_PAYLOAD);
  assert.strictEqual(elements.answerText.textContent, EMPTY_ANSWER, `${control}: stale answer stayed out`);
  assert.strictEqual(elements.dataSource.textContent, "waiting", `${control}: stale source stayed out`);
  assert.ok(!elements.answerText.textContent.includes(STALE_ANSWER), `${control}: stale text`);
}

async function runRenderedThenModeChange() {
  const { elements, pending } = boot();
  elements.askBtn.click();
  await tick();
  await resolveOldest(pending, STALE_PAYLOAD);
  assert.ok(elements.answerText.textContent.includes(STALE_ANSWER), "first response should render");
  elements.source.value = "service";
  elements.source.dispatchEvent({ type: "change" });
  await tick();
  assert.strictEqual(elements.fixtureChip.textContent, "服務");
  assert.strictEqual(elements.answerText.textContent, EMPTY_ANSWER);
  assert.strictEqual(elements.dataSource.textContent, "waiting");
  await resolveOldest(pending, STALE_PAYLOAD);
  assert.strictEqual(elements.answerText.textContent, EMPTY_ANSWER);
  assert.strictEqual(elements.dataSource.textContent, "waiting");
}

(async () => {
  await runControl("source", "service");
  await runControl("fixture", "conflict");
  await runControl("answerScope", "USB_2_0");
  await runControl("retrievalMode", "explicit_cross_scope");
  await runControl("allowedScopes", "USB_2_0, USB_3_X");
  await runRenderedThenModeChange();
  process.stdout.write("PASS\n");
})().catch((err) => {
  process.stderr.write(String(err && err.stack ? err.stack : err) + "\n");
  process.exit(1);
});
