// V0.10.2 twin-board UI test (run: node tools/test_web_ui.mjs).
// Loads web/index.html plus every site script in page order, then checks
// the succession setup controls, the phase-flip board with its blind
// faction cards, the search / support / galea modals, the claim-window
// banner, the no-boost contest duel, a full human-seat game, a bot-only
// game, and replay reset.
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

const scripts = [...html.matchAll(/<script src="([^"]+)"><\/script>/g)].map(m => m[1]);
check("page loads the V0.10.2 script set in order",
  JSON.stringify(scripts) === JSON.stringify(
    ["rules.js", "board-data.js", "engine.js", "succession-engine.js", "succession-bots.js", "app.js"]));
for (const f of scripts) window.eval(readFileSync(new URL(f, WEB), "utf8"));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const B = window.DIOCLET_BOARD;
const E = window.DIOCLET_ENGINE;
const K = c => c.join(",");
const gate2Transform = {};
for (const [id, c] of Object.entries(B.successionMap.gates)) {
  gate2Transform[id] = `translate(${36 + c[0] * 44 + 22},${36 + c[1] * 44 + 22})`;
}
check("board artifact is the V0.10.2 twin-board payload",
  B.rulesVersion === "0.10.2" && B.palaceMap && B.successionMap);

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
check("rulebook teaches the twin boards and the window",
  body.innerHTML.includes("succession map") &&
  body.innerHTML.includes("2 full rounds") &&
  body.innerHTML.includes("pugio"));
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
check("six distinct block labels", document.querySelectorAll(".palace-block").length === 6 &&
  new Set([...document.querySelectorAll(".palace-block")].map(b => b.dataset.district)).size === 6);
check("each district has exactly one reveal label", new Set(districtLabels().map(n => n.id)).size === 6);

// --- twin-board markers ---------------------------------------------
const palaceMarkers = document.getElementById("palace-markers");
const successionMarkers = document.getElementById("succession-markers");
check("phase 1 shows the palace layer only",
  palaceMarkers.getAttribute("display") === "inline" &&
  successionMarkers.getAttribute("display") === "none");
check("six face-down faction cards wait on the succession layer",
  [...successionMarkers.querySelectorAll('[id^="site-"]')].length === 6 &&
  [...successionMarkers.querySelectorAll('[id^="sitetext-"]')].every(t => t.textContent === "?"));
check("the south gate chip moves between maps",
  document.querySelector('[data-k="12,12"]').classList.contains("succession-site") &&
  document.querySelector('[data-k="6,12"]').classList.contains("palace-site"));
check("palace legend names the checkpoint",
  document.getElementById("checkpoint-key").textContent === "Checkpoint");
check("claim marker starts hidden",
  document.getElementById("claim-marker").getAttribute("display") === "none");
check("legend explains the faction cards",
  document.querySelector(".faction-key").textContent.includes("Revealed cards"));

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
}
const orderHumanFirst = game => {
  game.order = ["P0", "P1", "P2", "P3"];
  game.turnIndex = 0;
  game.turnRoundStart = 0;
};
const dealSites = (game, real = {}) => {
  game.factionSites = {};
  game.factionSitesRevealed = {};
  for (const c of B.successionMap.cardSpaces) game.factionSites[K(c)] = null;
  for (const [k, f] of Object.entries(real)) game.factionSites[k] = f;
};

// --- auto-collection at a treasure entry ----------------------------
const entryA = B.palaceMap.treasureEntries.A;
await startForcedGame(game => {
  orderHumanFirst(game);
  E.player(game, "P0").pos = K([entryA[0] + 1, entryA[1]]);
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
const treasureCell = document.querySelector(`[data-k="${K(entryA)}"]`);
check("forced treasure entry is reachable", treasureCell.classList.contains("reachable"));
check("treasure click area covers its visible marker and border",
  Number(treasureCell.getAttribute("r")) > 16.5 + 2.5 / 2);
treasureCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("treasure collects without a pointless choice",
  document.getElementById("choice-dialog").classList.contains("hidden"));
await sleep(50);
const collectorCard = [...document.querySelectorAll(".pcard")][0];
check("player card shows the V0.10.2 succession state",
  collectorCard.querySelector(".pstats").textContent.includes("Prestige 0/3") &&
  collectorCard.querySelector(".pstats").textContent.includes("Gear 1/6") &&
  collectorCard.querySelector(".support-list").textContent.includes("0/2 support"));
check("player card names the collected equipment",
  /^(Pugio|Pilum|Galea|Scutum|Gladius|Lorica)$/.test(
    collectorCard.querySelector(".gear-list").textContent.split("·")[1]?.trim()));

// A rival standing on the entry creates a real choice: collect or duel.
let choiceDestination, choiceGame;
await startForcedGame(game => {
  orderHumanFirst(game);
  E.player(game, "P0").pos = K([entryA[0] + 1, entryA[1]]);
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
  E.player(choiceGame, "P0").equipment.length === 0 && E.player(choiceGame, "P0").pos === K([entryA[0] + 1, entryA[1]]));
rivalCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
document.getElementById("choice-cancel").click();
check("Cancel button closes the modal", choiceDialog.classList.contains("hidden"));
rivalCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const collector = E.player(choiceGame, "P0");
[...document.querySelectorAll("#choice-actions button")].find(b => b.textContent.includes("Take the treasure")).click();
await sleep(50);
check("modal selection collects the treasure and closes", collector.equipment.length === 1 && choiceDialog.classList.contains("hidden"));

// --- the galea reveal modal ------------------------------------------
let galeaGame;
await startForcedGame(game => {
  orderHumanFirst(game);
  galeaGame = game;
  E.player(game, "P0").equipment = ["galea"];
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
const galeaCell = document.querySelector(`[data-k="${E.player(galeaGame, "P0").pos}"]`);
check("the galea highlights the player's own space", galeaCell.classList.contains("reachable"));
galeaCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("galea opens a district picker", !choiceDialog.classList.contains("hidden") &&
  [...document.querySelectorAll("#choice-actions button")]
    .filter(b => b.textContent.includes("reveal district")).length >= 1);
const hiddenDistrict = Object.keys(B.palaceMap.treasureEntries)
  .find(n => !(n in galeaGame.revealed));
[...document.querySelectorAll("#choice-actions button")]
  .find(b => b.textContent.includes("reveal district " + hiddenDistrict)).click();
await sleep(50);
check("galea reveals the chosen district",
  galeaGame.revealed[hiddenDistrict] === galeaGame.districtEquipment[hiddenDistrict] &&
  districtLabels().some(n => n.textContent !== "Hidden treasure"));

// --- searching a face-down faction card ------------------------------
const siteA = "3,0";
let searchGame;
await startForcedGame(game => {
  orderHumanFirst(game);
  searchGame = game;
  game.phase = 2;
  dealSites(game, { [siteA]: "officials" });
  E.player(game, "P0").pos = "4,0";
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
check("phase flip hides the palace layer and the treasure plates",
  palaceMarkers.getAttribute("display") === "none" &&
  successionMarkers.getAttribute("display") === "inline" &&
  [...document.querySelectorAll(".district-plate")].every(p => p.getAttribute("display") === "none"));
check("phase label reports the succession map",
  document.getElementById("phase-label").textContent === "Succession · Phase II");
check("the moved south gate grows its chip in phase 2",
  document.querySelector('[data-k="12,12"]').getAttribute("r") === "20" &&
  document.querySelector('[data-k="6,12"]').getAttribute("r") === "13");
check("checkpoint key becomes the Peristyle",
  document.getElementById("checkpoint-key").textContent === "Peristyle · claim");
const siteCell = document.querySelector(`[data-k="${siteA}"]`);
siteCell.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("an unoccupied card searches without a pointless walk choice",
  choiceDialog.classList.contains("hidden"));
await sleep(50);
check("the searched card turns face up as officials",
  document.getElementById("sitetext-" + siteA).textContent === "O" &&
  searchGame.factionSitesRevealed[siteA] === "officials");
check("a searched blank card would show the empty mark",
  [...document.querySelectorAll('[id^="sitetext-"]')].filter(t => t.textContent === "?").length === 5);

// --- buying support at a revealed card --------------------------------
let supportGame;
await startForcedGame(game => {
  orderHumanFirst(game);
  supportGame = game;
  game.phase = 2;
  dealSites(game, { [siteA]: "officials" });
  game.factionSitesRevealed = { [siteA]: "officials" };
  const p = E.player(game, "P0");
  p.pos = "4,0";
  p.prestige = 1;
  E.player(game, "P1").pos = siteA;
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
document.querySelector(`[data-k="${siteA}"]`).dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("support competes with a duel in the modal at a revealed card",
  !choiceDialog.classList.contains("hidden") &&
  document.getElementById("choice-actions").textContent.includes("Secure Imperial officials support") &&
  document.getElementById("choice-actions").textContent.includes("Duel"));
[...document.querySelectorAll("#choice-actions button")].find(b =>
  b.textContent.includes("Secure Imperial officials support")).click();
await sleep(50);
const supportCard = [...document.querySelectorAll(".pcard")][0];
check("support action spends Prestige and records the faction",
  supportCard.querySelector(".pstats").textContent.includes("Prestige 0/3") &&
  supportCard.querySelector(".support-list").textContent.includes("1/2 support") &&
  supportCard.querySelector(".fbadge")?.textContent === "O");

// --- proclaiming a claim -------------------------------------------
let proclaimGame;
await startForcedGame(game => {
  orderHumanFirst(game);
  proclaimGame = game;
  game.phase = 2;
  dealSites(game);
  game.factionSitesRevealed = { "3,0": "army" };
  const p = E.player(game, "P0");
  p.pos = "9,6";
  p.support = ["army", "elites"];
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
document.querySelector('[data-k="9,6"]').dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(50);
const claimBox = document.getElementById("claim-status");
check("proclaiming needs no modal when uncontested",
  choiceDialog.classList.contains("hidden") && !claimBox.hidden);
check("claim banner counts the window, not responses",
  claimBox.textContent.includes("Player 1 proclaims at the Peristyle") &&
  claimBox.textContent.includes("2 more full rounds") &&
  !claimBox.textContent.includes("responded"));
check("claim marker lights the Peristyle",
  document.getElementById("claim-marker").getAttribute("display") === "inline");
check("chronicle records the proclamation",
  document.getElementById("log").textContent.includes("proclaim"));

// --- contesting an active claim -------------------------------------
const savedContestCost = B.succession.contestFee;
B.succession.contestFee = 1;
let contestedGame;
await startForcedGame(game => {
  orderHumanFirst(game);
  contestedGame = game;
  game.phase = 2;
  dealSites(game);
  game.factionSitesRevealed = { "3,0": "army" };
  const p = E.player(game, "P0");
  p.pos = "7,6";
  p.prestige = 2;
  game.pendingClaim = { player: "P1", claimId: 99, claim_id: 99,
    round: game.round - 1, responded: [] };
  E.player(game, "P1").pos = "9,6";
  E.player(game, "P1").prestige = 1;
  game.diceOverrides = { combat: [6, 1] };
}, { P0: "human", P1: "human", P2: "human", P3: "human" });
check("claim banner shows one round left inside the window",
  !claimBox.hidden && claimBox.textContent.includes("1 more full round"));
document.querySelector('[data-k="8,6"]').dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const contestButtons = [...document.querySelectorAll("#choice-actions button")].filter(b =>
  b.textContent.includes("Contest Player 2"));
check("contest modal offers one duel with no paid boost",
  contestButtons.length === 1 &&
  contestButtons[0].textContent.includes("1 Prestige fee") &&
  ![...document.querySelectorAll("#choice-actions button")].some(b => b.textContent.includes("+2")));
contestButtons[0].click();
await sleep(80);
const winnerCard = [...document.querySelectorAll(".pcard")][0];
check("won contest cancels the claim",
  claimBox.hidden && document.getElementById("claim-marker").getAttribute("display") === "none");
check("fee and duel reward both apply",
  winnerCard.querySelector(".pstats").textContent.includes("Prestige 2/3"));
const loserPawn = document.getElementById("pawn-P1");
check("beaten claimant returns to the succession-map gate",
  loserPawn.getAttribute("transform") === gate2Transform[E.player(contestedGame, "P1").gateId]);
check("the beaten claimant pays the shame",
  E.player(contestedGame, "P1").prestige === 0);
B.succession.contestFee = savedContestCost;

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
  B.palaceMap.width * B.palaceMap.height - B.palaceMap.blocked.length);
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
const gateCell = document.querySelector(`[data-k="${K(B.palaceMap.gates.P0)}"]`);
check("gate cell has a tooltip",
  gateCell.querySelector("title")?.textContent.includes("Gate"));
const cpCell = document.querySelector(`[data-k="${K(B.palaceMap.checkpoint)}"]`);
check("checkpoint cell has a tooltip",
  cpCell.querySelector("title")?.textContent.includes("Checkpoint"));
const entryCell = document.querySelector(`[data-k="${K(B.palaceMap.treasureEntries.A)}"]`);
check("entry A cell has a tooltip",
  entryCell.querySelector("title")?.textContent.includes("Treasure entry"));
const cardCell = document.querySelector(`[data-k="${siteA}"]`);
check("card space carries its succession tooltip",
  cardCell.dataset.successionTitle.includes("search"));

// --- the human-seat loop --------------------------------------------
let sawHint = false, sawSuccession = false, usedKeyboard = false;
guard = 0;
while (document.getElementById("gameover")
         .classList.contains("hidden") && guard < 4000) {
  guard++;
  if (document.getElementById("phase-label").textContent === "Succession · Phase II") sawSuccession = true;
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
document.getElementById("againbtn").click();
check("replay hides all treasure cards", districtLabels().every(n => n.textContent === "Hidden treasure"));
check("replay restores the palace phase",
  document.getElementById("phase-label").textContent === "Palace · Phase I" &&
  document.getElementById("checkpoint-key").textContent === "Checkpoint" &&
  palaceMarkers.getAttribute("display") === "inline" &&
  successionMarkers.getAttribute("display") === "none");
check("replay turns every faction card face down",
  [...document.querySelectorAll('[id^="sitetext-"]')].every(t => t.textContent === "?"));
// Resetting the table also restores every pawn to a palace gate.
const pawnTransforms = ["P0", "P1", "P2", "P3"].map(id =>
  document.getElementById("pawn-" + id).getAttribute("transform"));
const palaceGateTransforms = Object.values(B.palaceMap.gates).map(c =>
  `translate(${36 + c[0] * 44 + 22},${36 + c[1] * 44 + 22})`).sort();
check("replay restores pawns to the four palace gates",
  JSON.stringify(pawnTransforms.sort()) === JSON.stringify(palaceGateTransforms));

if (failures) { console.error(failures + " failures"); process.exit(1); }
console.log("all V0.10.2 twin-board UI tests pass");

// No dom.window.close(): a pending bot timer can fire after the
// window tears down and crash the run after all checks passed.
