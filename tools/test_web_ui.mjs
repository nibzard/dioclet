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

// --- dialog access from setup --------------------------------------
const setupRules = document.getElementById("setup-rulesbtn");
setupRules.focus();
setupRules.click();
check("rulebook opens from setup", !overlay.classList.contains("hidden"));
check("rulebook receives focus", document.activeElement === overlay);
document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape" }));
check("Escape returns focus to setup", document.activeElement === setupRules);
check("setup remains open", !document.getElementById("setup").classList.contains("hidden"));

const districtLabels = () => [...document.querySelectorAll('[id^="district-"]')];
check("six hidden district cards", districtLabels().length === 6 &&
  districtLabels().every(n => n.textContent === "Hidden treasure"));

// --- take a treasure as a human -------------------------------------
for (const id of ["P0", "P1", "P2", "P3"]) {
  document.getElementById("kind-" + id).value = "human";
}
document.getElementById("startbtn").click();
const treasureCell = Object.values(window.DIOCLET_BOARD.districts)
  .map(c => document.querySelector(`[data-k="${c.join(",")}"]`))
  .find(c => c.classList.contains("reachable"));
check("a treasure is reachable in the test turn", Boolean(treasureCell));
if (treasureCell) {
  check("treasure click area covers its visible marker and border",
    Number(treasureCell.getAttribute("r")) > 16.5 + 2.5 / 2);
  const playerIndex = [...document.querySelectorAll(".pcard")].findIndex(c => c.classList.contains("active"));
  treasureCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  check("treasure collects without a pointless choice",
    document.getElementById("choice-dialog").classList.contains("hidden"));
  await sleep(50);
  check("human collects the treasure",
    document.querySelectorAll(".pcard")[playerIndex].querySelector(".pstats").textContent.includes("1/6"));
}
// A rival at the entry creates a real choice: collect or duel.
const engine = window.DIOCLET_ENGINE;
const newGame = engine.newGame;
let choiceGame, choiceDestination;
engine.newGame = (...args) => {
  choiceGame = newGame(...args);
  choiceDestination = engine.legalActions(choiceGame).find(a => a.kind === "explore").dest;
  choiceGame.players.find(p => p.id !== engine.active(choiceGame).id).pos = choiceDestination;
  return choiceGame;
};
document.getElementById("startbtn").click();
engine.newGame = newGame;
const rivalCell = document.querySelector(`[data-k="${choiceDestination}"]`);
rivalCell.focus();
rivalCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const choiceDialog = document.getElementById("choice-dialog");
check("competing actions open a modal", !choiceDialog.classList.contains("hidden"));
check("treasure modal omits the walk action", !document.getElementById("choice-actions").textContent.includes("Just walk"));
check("treasure modal offers collection and a duel",
  document.getElementById("choice-actions").textContent.includes("Take the treasure") &&
  document.getElementById("choice-actions").textContent.includes("Duel"));
check("modal focuses its first action", document.activeElement === document.querySelector("#choice-actions button"));
document.dispatchEvent(new window.KeyboardEvent("keydown", {key: "Escape"}));
check("Escape cancels the choice and restores board focus", choiceDialog.classList.contains("hidden") && document.activeElement === rivalCell);
check("canceling does not spend the turn", engine.active(choiceGame).equipment.length === 0);
rivalCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
document.getElementById("choice-cancel").click();
check("Cancel button closes the modal", choiceDialog.classList.contains("hidden"));
rivalCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const collector = engine.active(choiceGame);
[...document.querySelectorAll("#choice-actions button")].find(b => b.textContent.includes("Take the treasure")).click();
await sleep(50);
check("modal selection collects the treasure and closes", collector.equipment.length === 1 && choiceDialog.classList.contains("hidden"));

// Restore the normal human-and-bots table for the full game below.
document.getElementById("kind-P1").value = "balanced";
document.getElementById("kind-P2").value = "balanced";
document.getElementById("kind-P3").value = "greedy";

// --- start a game ---------------------------------------------------
document.getElementById("seed").value = "2026";
document.getElementById("startbtn").click();
await sleep(50);
check("setup overlay hidden after start",
  document.getElementById("setup").classList.contains("hidden"));
check("all board street spaces render", document.querySelectorAll(".cell").length ===
  window.DIOCLET_BOARD.width * window.DIOCLET_BOARD.height - window.DIOCLET_BOARD.blocked.length);
check("4 pawns placed", document.querySelectorAll(".pawn").length === 4);
const zoom = document.getElementById("zoom-board");
zoom.click();
check("board zoom reports its enlarged state", document.getElementById("boardwrap").classList.contains("is-zoomed") && zoom.getAttribute("aria-pressed") === "true");
zoom.click();
check("board returns to overview", !document.getElementById("boardwrap").classList.contains("is-zoomed"));

// --- click-through and tooltips ------------------------------------
const chips = [...document.querySelectorAll("svg circle")].filter(
  c => c.getAttribute("r") === "16.5");
check("all special chips pass clicks through",
  chips.length >= 12 && chips.every(c =>
    c.getAttribute("pointer-events") === "none"));
check("pawns pass clicks through",
  [...document.querySelectorAll(".pawn")].every(p =>
    p.getAttribute("pointer-events") === "none"));
const gateCell = document.querySelector(`[data-k="${window.DIOCLET_BOARD.gates.P0.join(",")}"]`);
check("gate cell has a tooltip",
  gateCell.querySelector("title")?.textContent.includes("Gate"));
const cpCell = document.querySelector(`[data-k="${window.DIOCLET_BOARD.checkpoint.join(",")}"]`);
check("checkpoint cell has a tooltip",
  cpCell.querySelector("title")?.textContent.includes("Checkpoint"));
const entryCell = document.querySelector(`[data-k="${window.DIOCLET_BOARD.districts.A.join(",")}"]`);
check("entry A cell has a tooltip",
  entryCell.querySelector("title")?.textContent.includes("Treasure entry"));

// --- play a full game as seat P0 (human) ----------------------------
let sawHint = false, guard = 0, usedKeyboard = false;
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
    if (!usedKeyboard) {
      check("available moves support keyboard access", cell.getAttribute("tabindex") === "0" && cell.getAttribute("role") === "button");
      cell.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
      usedKeyboard = true;
    } else {
      cell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    }
    await sleep(20);
    // If a choice menu appeared, take the first button.
    const btn = !choiceDialog.classList.contains("hidden") && document.querySelector("#choice-actions button.choice");
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

check("keyboard move completes", usedKeyboard);
check("collected treasure appears in its district", districtLabels().some(n => n.textContent !== "Hidden treasure"));
document.getElementById("againbtn").click();
check("replay hides all treasure cards", districtLabels().every(n => n.textContent === "Hidden treasure"));
// Resetting the table also restores every pawn to its gate.
const board = window.DIOCLET_BOARD;
check("replay restores pawn positions", Object.entries(board.gates).every(([id, [x, y]]) =>
  document.getElementById("pawn-" + id).getAttribute("transform") === `translate(${36 + x * 44 + 22},${36 + y * 44 + 22})`));

if (failures) { console.error(failures + " failures"); process.exit(1); }
console.log("all UI smoke tests pass");

// No dom.window.close(): a pending bot timer can fire after the
// window tears down and crash the run after all checks passed.

