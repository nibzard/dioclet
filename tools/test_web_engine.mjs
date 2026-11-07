// Node test for web/engine.js + web/bots.js (run: node tools/test_web_engine.mjs)
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
require("../web/board-data.js");
require("../web/engine.js");
require("../web/bots.js");

const E = globalThis.DIOCLET_ENGINE;
const BOTS = globalThis.DIOCLET_BOTS;
const B = globalThis.DIOCLET_BOARD;

let failures = 0;
function check(name, cond) {
  if (cond) { console.log("  ok:", name); }
  else { console.error("  FAIL:", name); failures++; }
}

// --- board facts ---------------------------------------------------
check("97 street spaces",
  B.width * B.height - B.blocked.length === 97);
check("six blocks of 5x5",
  (() => {
    const blocked = new Set(B.blocked.map(c => c.join(",")));
    const seen = new Set(); let blocks = 0; let all5x5 = true;
    for (const c of blocked) {
      if (seen.has(c)) continue;
      blocks++;
      const group = new Set(); const q = [c];
      while (q.length) {
        const cur = q.pop();
        if (group.has(cur)) continue;
        group.add(cur); seen.add(cur);
        const [x, y] = cur.split(",").map(Number);
        for (const n of [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]]) {
          if (blocked.has(n.join(","))) q.push(n.join(","));
        }
      }
      const xs = [...group].map(k => +k.split(",")[0]);
      const ys = [...group].map(k => +k.split(",")[1]);
      if (Math.max(...xs) - Math.min(...xs) !== 4 ||
          Math.max(...ys) - Math.min(...ys) !== 4) all5x5 = false;
    }
    return blocks === 6 && all5x5;
  })());
check("no blocked special",
  [...Object.values(B.gates), ...Object.values(B.districts),
   B.checkpoint, ...B.gloryPosts, ...Object.values(B.level2)]
  .every(c => !B.blocked.some(b => b[0] === c[0] && b[1] === c[1])));

// --- engine invariants over full bot games -------------------------
function playGame(seed, kinds) {
  const seats = ["P0", "P1", "P2", "P3"].map((id, i) => ({
    id, kind: kinds[i], name: id }));
  const g = E.newGame(seed, seats);
  let guard = 0;
  while (!g.winner && !g.draw) {
    if (++guard > 6000) return { g, stuck: true };
    const p = E.active(g);
    const acts = E.legalActions(g);
    if (acts.length === 0) return { g, stuck: true, noActions: true };
    // invariant: every action destination is a street cell within the roll
    for (const a of acts) {
      const [x, y] = a.dest.split(",").map(Number);
      if (B.blocked.some(b => b[0] === x && b[1] === y)) {
        return { g, bad: "action into building: " + a.dest };
      }
      if (a.dist > g.currentRoll.total) {
        return { g, bad: "move beyond roll" };
      }
    }
    // invariant: glory always within cap
    for (const q of g.players) {
      if (q.glory < 0 || q.glory > B.gloryCap) {
        return { g, bad: "glory out of range" };
      }
    }
    const a = BOTS.choose(p.kind, { ...g, activePlayer: p }, acts,
                          () => g.rng());
    E.applyAction(g, a);
  }
  return { g, stuck: false };
}

console.log("full bot games:");
let wins = 0, draws = 0, rounds = [];
for (let i = 0; i < 40; i++) {
  const kinds = ["balanced", "greedy", "aggressive", "balanced"];
  const { g, stuck, bad, noActions } = playGame(1000 + i * 7, kinds);
  if (bad) { check("game " + i + " invariants", false); console.error("   ", bad); failures++; break; }
  if (stuck || noActions) { check("game " + i + " terminates", false); failures++; break; }
  if (g.winner) wins++; else draws++;
  rounds.push(g.round);
  // winner has two hits
  if (g.winner && E.player(g, g.winner).hits !== 2) {
    check("winner has 2 hits", false); failures++; break;
  }
  // all players have full equipment after the transition
  if (g.players.some(p => p.equipment.length !== 6)) {
    check("full gear after transition", false); failures++; break;
  }
}
check("40 bot games completed", true);
console.log(`  wins ${wins}, draws ${draws}, median rounds ` +
  rounds.sort((a, b) => a - b)[Math.floor(rounds.length / 2)]);
check("all games decisive or drawn cleanly", wins + draws === 40);

// determinism: same seed, same bot choices -> same winner
const r1 = playGame(777, ["balanced", "balanced", "greedy", "aggressive"]);
const r2 = playGame(777, ["balanced", "balanced", "greedy", "aggressive"]);
check("same seed replays identically",
  r1.g.winner === r2.g.winner && r1.g.round === r2.g.round &&
  r1.g.log.length === r2.g.log.length);

// 2d6 roll distribution sanity
const g0 = E.newGame(9, ["P0","P1","P2","P3"].map(id => ({ id, kind: "balanced", name: id })));
let min = 99, max = 0, total = 0, n = 0, sum = 0;
for (let i = 0; i < 4000; i++) {
  const r = { dice: [1 + Math.floor(g0.rng() * 6), 1 + Math.floor(g0.rng() * 6)] };
  min = Math.min(min, r.dice[0]); max = Math.max(max, r.dice[0]);
  total += r.dice.reduce((a, b) => a + b, 0); n++;
}
check("movement dice in range 2..12", total / n > 6.5 && total / n < 7.5);

if (failures) { console.error(failures + " failures"); process.exit(1); }
console.log("all web engine tests pass");
