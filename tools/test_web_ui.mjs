// V0.8 succession UI test (run: node tools/test_web_ui.mjs).
// Loads web/index.html plus every site script in page order, then checks
// the succession setup controls, action modals, claim UI, a full
// human-seat game, a bot-only game, and replay reset.
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
                 "succession-engine.js", "succession-bots.js", "app.js"]) {
  window.eval(readFileSync(new URL(f, WEB), "utf8"));
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const B = window.DIOCLET_BOARD;
const E = window.DIOCLET_ENGINE;
const K = c => c.join(",");
const gateTransform = {}
for (const [id, c] of Object.entries(B.gates)) {
  gateTransform[id] = `translate(${36 + c[0] * 44 + 22},${36 + c[1] * 44 + 22})`;
}
check("board artifact is the V0.8 succession mode", B.mode === "succession-v1");

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
check("rulebook teaches the succession claim",
  body.innerHTML.includes("proclaim your claim") &&
  body.innerHTML.includes("acclaimed emperor"));
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
check("six distinct block labels", document.querySelectorAll(".city-block").length === 6 &&
  new Set([...document.querySelectorAll(".city-block")].map(b => b.dataset.district)).size === 6);
check("each district has exactly one reveal label", new Set(districtLabels().map(n => n.id)).size === 6);

// --- phase-specific board markers ----------------------------------
const palaceMarkers = document.getElementById("palace-markers");
check("palace markers stay hidden in succession mode",
  palaceMarkers.getAttribute("display") === "none" &&
  palaceMarkers.querySelectorAll("circle").length === 0);
check("legacy Emperor legend never shows", [...document.querySelectorAll("[data-phase='2']")].every(e => e.hidden));
check("city legend names the checkpoint", document.getElementById("checkpoint-key").textContent === "Checkpoint");
const factionMarkers = document.getElementById("faction-markers");
check("faction badges render in the city phase",
  factionMarkers.getAttribute("display") === "inline" &&
  ["A", "O", "C"].every(t => factionMarkers.textContent.includes(t)));
check("claim marker starts hidden",
  document.getElementById("claim-marker").getAttribute("display") === "none");
check("legend explains the faction badges",
  document.querySelector(".faction-key").textContent.includes("Army"));

// --- gate assignment controls --------------------------------------
const gateMode = document.getElementById("gate-mode");
const startbtn = document.getElementById("startbtn");
const previews = () => ["P0", "P1", "P2", "P3"].map(id =>
  document.getElementById("gate-preview-" + id).textContent);
check("random mode previews every gate",
  gateMode.value === "random" &&
  previews().every(t => t.startsWith("Starts at ")) && !startbtn.disabled);
const firstPreview = previews();
document.getElementById("seed").value = "777";
document.getElementById("seed").dispatchEvent(new window.Event("input"));
check("another seed still previews four gates",
  previews().every(t => t.startsWith("Starts at ")) && !startbtn.disabled);
document.getElementById("seed").value = "2026";
document.getElementById("seed").dispatchEvent(new window.Event("input"));
check("same seed reproduces the assignment", JSON.stringify(previews()) === JSON.stringify(firstPreview));

gateMode.value = "manual";
gateMode.dispatchEvent(new window.Event("change"));
check("manual mode shows the gate selects",
  !document.getElementById("gate-P0").hidden && !startbtn.disabled);
document.getElementById("gate-P1").value = "P0";
document.getElementById("gate-P1").dispatchEvent(new window.Event("change"));
check("duplicate gates block the start",
  startbtn.disabled && document.getElementById("setup-error").textContent.length > 0);
document.getElementById("gate-P1").value = "P1";
document.getElementById("gate-P1").dispatchEvent(new window.Event("change"));
check("distinct manual gates clear the error",
  !startbtn.disabled && document.getElementById("setup-error").textContent === "");
gateMode.value = "rotation";
gateMode.dispatchEvent(new window.Event("change"));
check("rotation mode shows the rotation select",
  !document.getElementById("rotation-label").hidden);
document.getElementById("gate-rotation").value = "1";
document.getElementById("gate-rotation").dispatchEvent(new window.Event("change"));
check("rotation preview shifts every player one gate",
  previews()[0] === "Starts at East · Silver" && previews()[3] === "Starts at North · Golden");
gateMode.value = "random";
gateMode.dispatchEvent(new window.Event("change"));

// Helper: start a game with the human seat forced into a specific
// state, by wrapping engine.newGame for the duration of the click.
const newGame = E.newGame;
async function startForcedGame(mutate, kinds) {
  for (const [id, kind] of Object.entries(kinds || {})) {
    document.getElementById("kind-" + id).value = kind;
  }
  E.newGame = (...args) => {
    const game = newGame(...args);
    mutate(game);
    return game;
  };
  startbtn.click();
  E.newGame = newGame;
  await sleep(30);
  return null;
}
const orderHumanFirst = game => {
  game.order = ["P0", "P1", "P2", "P3"];
  game.turnIndex = 0;
  game.turnRoundStart = 0;
};

// --- auto-collection at a treasure entry ----------------------------
await startForcedGame(game => {
  orderHumanFirst(game);
  E.player(game, "P0").pos = "4,0";
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
const treasureCell = document.querySelector('[data-k="3,0"]');
check("forced treasure entry is reachable", treasureCell.classList.contains("reachable"));
check("treasure click area covers its visible marker and border",
  Number(treasureCell.getAttribute("r")) > 16.5 + 2.5 / 2);
treasureCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("treasure collects without a pointless choice",
  document.getElementById("choice-dialog").classList.contains("hidden"));
await sleep(50);
const collectorCard = [...document.querySelectorAll(".pcard")][0];
check("player card shows the V0.8 succession state",
  collectorCard.querySelector(".pstats").textContent.includes("Prestige 0/3") &&
  collectorCard.querySelector(".pstats").textContent.includes("Gear 1/6") &&
  collectorCard.querySelector(".support-list").textContent.includes("0/2 support"));

// A rival standing on the entry creates a real choice: collect or duel.
let choiceDestination, choiceGame;
await startForcedGame(game => {
  orderHumanFirst(game);
  E.player(game, "P0").pos = "4,0";
  choiceDestination = E.legalActions(game).find(a => a.kind === "explore").dest;
  E.player(game, "P1").pos = choiceDestination;
  choiceGame = game;
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
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
check("canceling does not spend the turn",
  E.player(choiceGame, "P0").equipment.length === 0 && E.player(choiceGame, "P0").pos === "4,0");
rivalCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
document.getElementById("choice-cancel").click();
check("Cancel button closes the modal", choiceDialog.classList.contains("hidden"));
rivalCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const collector = E.player(choiceGame, "P0");
[...document.querySelectorAll("#choice-actions button")].find(b => b.textContent.includes("Take the treasure")).click();
await sleep(50);
check("modal selection collects the treasure and closes", collector.equipment.length === 1 && choiceDialog.classList.contains("hidden"));

// --- faction support is a real action -------------------------------
await startForcedGame(game => {
  orderHumanFirst(game);
  const p = E.player(game, "P0");
  p.pos = "6,5";
  p.prestige = 1;
  E.player(game, "P1").pos = "6,6";
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
const peristyleCell = document.querySelector('[data-k="6,6"]');
peristyleCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("support competes with a duel in the modal",
  !choiceDialog.classList.contains("hidden") &&
  document.getElementById("choice-actions").textContent.includes("Secure Imperial officials support"));
[...document.querySelectorAll("#choice-actions button")].find(b =>
  b.textContent.includes("Secure Imperial officials support")).click();
await sleep(50);
const supportCard = [...document.querySelectorAll(".pcard")][0];
check("support action spends Prestige and records the faction",
  supportCard.querySelector(".pstats").textContent.includes("Prestige 0/3") &&
  supportCard.querySelector(".support-list").textContent.includes("1/2 support") &&
  supportCard.querySelector(".support-list").textContent.includes("Imperial officials"));

// --- proclaiming a claim -------------------------------------------
await startForcedGame(game => {
  orderHumanFirst(game);
  const p = E.player(game, "P0");
  p.pos = "6,6";
  p.support = ["army", "elites"];
  game.phase = 2;
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
check("phase label reports succession",
  document.getElementById("phase-label").textContent === "Palace · Succession");
document.querySelector('[data-k="6,6"]').dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(50);
const claimBox = document.getElementById("claim-status");
check("proclaiming needs no modal when uncontested",
  choiceDialog.classList.contains("hidden") && !claimBox.hidden);
check("claim status names the claimant and the responses",
  claimBox.textContent.includes("Player 1 claims the throne") &&
  claimBox.textContent.includes("0/3 rivals have responded"));
check("claim marker lights the Peristyle",
  document.getElementById("claim-marker").getAttribute("display") === "inline");
check("chronicle records the proclamation",
  document.getElementById("log").textContent.includes("claims imperial power"));

// --- contesting an active claim -------------------------------------
const savedContestCost = B.succession.contest_cost;
B.succession.contest_cost = 1;
let contestedGame;
await startForcedGame(game => {
  orderHumanFirst(game);
  const p = E.player(game, "P0");
  p.pos = "6,4";
  p.prestige = 2;
  game.phase = 2;
  game.pendingClaim = { claimant: "P1", player: "P1", responded: ["P2"],
                        id: 99, claim_id: 99 };
  E.player(game, "P1").pos = "6,6";
  game.diceOverrides = { combat: [6, 1] };
  contestedGame = game;
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
check("claim banner shows a partial response",
  !claimBox.hidden && claimBox.textContent.includes("1/3 rivals have responded"));
document.querySelector('[data-k="6,6"]').dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const contestButtons = [...document.querySelectorAll("#choice-actions button")].filter(b =>
  b.textContent.includes("Contest Player 2"));
check("contest modal prices the mandatory fee and the boost",
  contestButtons.length === 2 &&
  contestButtons.some(b => b.textContent.includes("· 1 Prestige")) &&
  contestButtons.some(b => b.textContent.includes("· 2 Prestige") && b.textContent.includes("+2")));
contestButtons.find(b => b.textContent.includes("· 1 Prestige")).click();
await sleep(80);
const winnerCard = [...document.querySelectorAll(".pcard")][0];
check("won contest cancels the claim",
  claimBox.hidden && document.getElementById("claim-marker").getAttribute("display") === "none" &&
  document.getElementById("log").textContent.includes("loses the claim"));
check("fee and duel reward both apply",
  winnerCard.querySelector(".pstats").textContent.includes("Prestige 2/3"));
const loserPawn = document.getElementById("pawn-P1");
check("beaten claimant returns to the assigned gate",
  loserPawn.getAttribute("transform") === gateTransform[E.player(contestedGame, "P1").gateId]);
B.succession.contest_cost = savedContestCost;

// --- watch four bots finish a whole game ----------------------------
document.getElementById("watchbtn").click();
let guard = 0;
while (document.getElementById("gameover").classList.contains("hidden") && guard < 3000) {
  guard++;
  await sleep(20);
}
check("bot-only game reaches the game-over overlay",
  !document.getElementById("gameover").classList.contains("hidden"));
const botline = document.getElementById("overline").textContent;
check("bot game reports a succession outcome",
  botline.includes("acclaimed emperor") || botline.includes("draw"));

// --- play a full game as seat P0 (human) ----------------------------
document.getElementById("setupbtn").click();
await sleep(20);
for (const id of ["P0", "P1", "P2", "P3"]) {
  document.getElementById("kind-" + id).value = "human";
}
document.getElementById("kind-P1").value = "balanced";
document.getElementById("kind-P2").value = "balanced";
document.getElementById("kind-P3").value = "greedy";
document.getElementById("seed").value = "2026";
document.getElementById("seed").dispatchEvent(new window.Event("input"));
document.getElementById("startbtn").click();
await sleep(50);
check("setup overlay hidden after start",
  document.getElementById("setup").classList.contains("hidden"));
check("all board street spaces render", document.querySelectorAll(".cell").length ===
  B.width * B.height - B.blocked.length);
check("4 pawns placed", document.querySelectorAll(".pawn").length === 4);
const zoom = document.getElementById("zoom-board");
zoom.click();
check("board zoom reports its enlarged state", document.getElementById("boardwrap").classList.contains("is-zoomed") && zoom.getAttribute("aria-pressed") === "true");
zoom.click();
check("board zoom toggles back to overview", !document.getElementById("boardwrap").classList.contains("is-zoomed"));

// --- click-through and tooltips ------------------------------------
const chips = [...document.querySelectorAll("svg circle")].filter(
  c => c.getAttribute("r") === "16.5");
check("all special chips pass clicks through",
  chips.length >= 12 && chips.every(c =>
    c.getAttribute("pointer-events") === "none"));
check("pawns pass clicks through",
  [...document.querySelectorAll(".pawn")].every(p =>
    p.getAttribute("pointer-events") === "none"));
const gateCell = document.querySelector(`[data-k="${K(B.gates.P0)}"]`);
check("gate cell has a tooltip",
  gateCell.querySelector("title")?.textContent.includes("Gate"));
const cpCell = document.querySelector(`[data-k="${K(B.checkpoint)}"]`);
check("checkpoint cell has a tooltip",
  cpCell.querySelector("title")?.textContent.includes("Checkpoint"));
const entryCell = document.querySelector(`[data-k="${K(B.districts.A)}"]`);
check("entry A cell has a tooltip",
  entryCell.querySelector("title")?.textContent.includes("Treasure entry"));
const elitesCell = document.querySelector(`[data-k="${K(B.succession.factions.elites)}"]`);
check("faction site explains the support action",
  elitesCell.querySelector("title")?.textContent.includes("City elites"));

// --- the human-seat loop --------------------------------------------
let sawHint = false, sawSuccession = false, usedKeyboard = false;
guard = 0;
while (document.getElementById("gameover")
         .classList.contains("hidden") && guard < 4000) {
  guard++;
  if (document.getElementById("phase-label").textContent === "Palace · Succession") sawSuccession = true;
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
    await sleep(60);
  } else {
    await sleep(20);
  }
}
await sleep(200);
check("game reached the game-over overlay",
  !document.getElementById("gameover").classList.contains("hidden"));
check("human turn hint shown at least once", sawHint);
check("game reached the succession phase", sawSuccession);
const overline = document.getElementById("overline").textContent;
check("game-over declares a succession outcome",
  overline.includes("acclaimed emperor") || overline.includes("draw"));

check("keyboard move completes", usedKeyboard);
check("collected treasure appears in its district", districtLabels().some(n => n.textContent !== "Hidden treasure"));
document.getElementById("againbtn").click();
check("replay hides all treasure cards", districtLabels().every(n => n.textContent === "Hidden treasure"));
check("replay restores the city phase",
  document.getElementById("phase-label").textContent === "City · Preparation" &&
  document.getElementById("checkpoint-key").textContent === "Checkpoint" &&
  palaceMarkers.getAttribute("display") === "none");
// Resetting the table also restores every pawn to a distinct gate.
const pawnTransforms = ["P0", "P1", "P2", "P3"].map(id =>
  document.getElementById("pawn-" + id).getAttribute("transform")).sort();
check("replay restores pawns to the four gates",
  JSON.stringify(pawnTransforms) === JSON.stringify(Object.values(gateTransform).sort()));

if (failures) { console.error(failures + " failures"); process.exit(1); }
console.log("all V0.8 succession UI tests pass");

// No dom.window.close(): a pending bot timer can fire after the
// window tears down and crash the run after all checks passed.
