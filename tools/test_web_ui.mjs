// UI smoke test for the web board (run: node tools/test_web_ui.mjs).
// Loads web/index.html plus the site scripts in jsdom, then plays a
// full game in the human seat using only board clicks.
//
// Requires jsdom: `npm install jsdom` in this repo or in the
// directory you run from. Prints SKIP (exit 0) when jsdom is
// not resolvable.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch {
  try {
    const mod = createRequire(process.cwd() + "/")("jsdom");
    JSDOM = mod.JSDOM || mod;
  } catch {
    console.log("SKIP: jsdom not installed (npm install jsdom)");
    process.exit(0);
  }
}

const WEB = new URL("../web/", import.meta.url);
const html = readFileSync(new URL("index.html", WEB), "utf8");
const dom = new JSDOM(html, { url: "https://dioclet-board.test/",
                              pretendToBeVisual: true,
                              runScripts: "outside-only" });
const { window } = dom;
const { document } = window;

let failures = 0;
const check = (name, cond) => {
  if (cond) console.log("  ok:", name);
  else { console.error("  FAIL:", name); failures++; }
};

// Speed the game up: every timer fires after 1ms.
window.setTimeout = (fn) => setTimeout(fn, 1);
window.clearTimeout = (id) => clearTimeout(id);

for (const f of ["rules.js", "board-data.js", "engine.js", "bots.js",
                 "app.js"]) {
  window.eval(readFileSync(new URL(f, WEB), "utf8"));
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// --- rules overlay --------------------------------------------------
const overlay = document.getElementById("rules");
const body = document.getElementById("rulesbody");
check("rules content injected", body.innerHTML.includes(
  "The game in one minute"));
check("overlay starts hidden", overlay.classList.contains("hidden"));
document.getElementById("rulesbtn").click();
check("rules button opens overlay", !overlay.classList.contains("hidden"));
check("rulebook has 10 sections",
  (body.innerHTML.match(/<h2>/g) || []).length === 10);
document.getElementById("rulesclose").click();
check("close button hides overlay", overlay.classList.contains("hidden"));

// --- start a game ---------------------------------------------------
document.getElementById("seed").value = "2026";
document.getElementById("startbtn").click();
await sleep(50);
check("setup overlay hidden after start",
  document.getElementById("setup").classList.contains("hidden"));
check("97 street circles", document.querySelectorAll(".cell").length === 97);
check("4 pawns placed", document.querySelectorAll(".pawn").length === 4);

// --- click-through and tooltips ------------------------------------
const chips = [...document.querySelectorAll("svg circle")].filter(
  c => c.getAttribute("r") === "16.5");
check("all special chips pass clicks through",
  chips.length >= 12 && chips.every(c =>
    c.getAttribute("pointer-events") === "none"));
check("pawns pass clicks through",
  [...document.querySelectorAll(".pawn")].every(p =>
    p.getAttribute("pointer-events") === "none"));
const gateCell = document.querySelector('[data-k="9,0"]');
check("gate cell has a tooltip",
  gateCell.querySelector("title")?.textContent.includes("Gate"));
const cpCell = document.querySelector('[data-k="9,6"]');
check("checkpoint cell has a tooltip",
  cpCell.querySelector("title")?.textContent.includes("Checkpoint"));
const entryCell = document.querySelector('[data-k="3,0"]');
check("entry A cell has a tooltip",
  entryCell.querySelector("title")?.textContent.includes("Treasure entry"));

// --- play a full game as seat P0 (human) ----------------------------
let sawHint = false, guard = 0;
while (document.getElementById("gameover")
         .classList.contains("hidden") && guard < 900) {
  guard++;
  const turn = document.getElementById("turnline").textContent;
  if (turn.includes("your turn")) {
    const hint = document.querySelector("#actionbox .hint");
    if (hint && hint.textContent.includes("You rolled")) sawHint = true;
    // Click the first reachable cell that has actions.
    const cell = document.querySelector(".cell.reachable");
    if (!cell) break;
    cell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    await sleep(20);
    // If a choice menu appeared, take the first button.
    const btn = document.querySelector("#actionbox button.choice");
    if (btn) { btn.click(); await sleep(20); }
    await sleep(150);
  } else {
    await sleep(30);
  }
}
await sleep(300);
check("game reached the game-over overlay",
  !document.getElementById("gameover").classList.contains("hidden"));
check("human turn hint shown at least once", sawHint);
const overline = document.getElementById("overline").textContent;
check("game-over declares an outcome",
  overline.includes("rules the palace") || overline.includes("draw"));

if (failures) { console.error(failures + " failures"); process.exit(1); }
console.log("all UI smoke tests pass");
