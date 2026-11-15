// V0.10.2 succession engine invariants: abilities and duels, blind
// faction cards, the twin-board transition, and the two-round claim
// window. Full Python parity lives in test_succession_parity.mjs; this
// file pins the mechanics with hand-built positions and injected dice.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const root = new URL('../', import.meta.url);
const plain = v => JSON.parse(JSON.stringify(v));
function loadScripts() {
  const ctx = vm.createContext({console, structuredClone});
  for (const f of ['board-data.js','engine.js','succession-engine.js'])
    vm.runInContext(readFileSync(new URL('web/'+f,root),'utf8'),ctx);
  return ctx.DIOCLET_ENGINE;
}
function loadBoard() {
  const ctx = vm.createContext({console});
  vm.runInContext(readFileSync(new URL('web/board-data.js',root),'utf8'),ctx);
  return ctx.DIOCLET_BOARD;
}
const E = loadScripts();
const BOARD = loadBoard();
const seats = ['P0','P1','P2','P3'].map(id => ({id, name:id, kind:'human'}));
const mk = (seed=7, opts) => E.newGame(seed, seats, opts);
const find = (g, kind, pred=a=>true) => E.legalActions(g).find(a => a.kind===kind && pred(a));
const EQUIP = ['pugio','pilum','galea','scutum','gladius','lorica_segmentata'];

// Setup and start reveals.
{
  const g = mk();
  assert.equal(Object.keys(g.districtEquipment).length, 6);
  assert.equal(Object.keys(g.revealed).length, 2);
  assert.deepEqual(g.setupReveals, g.setupReveals.slice().sort());
  assert.equal(g.factionSites, null, 'no faction sites before the change');
  const g2 = mk();
  assert.deepEqual(plain(g.districtEquipment), plain(g2.districtEquipment));
  assert.deepEqual(plain(g.rngStates), plain(g2.rngStates), 'same seed, same streams');
}

// The twin-board transition: gates reset on the succession map, the
// blind deal puts three factions on six card spaces, and property is kept.
function runToPhase2(g) {
  g.firstClaimer = 'P0'; g.triggerRound = g.round;
  g.transitionAt = Math.min(g.round + 1, 24);
  let guard = 0;
  while (g.phase === 1 && guard++ < 40) E.applyAction(g, E.legalActions(g)[0]);
  assert.equal(g.phase, 2);
  return g;
}
{
  const g = mk();
  const a = E.active(g);
  a.equipment = EQUIP.slice();
  a.prestige = 2;
  runToPhase2(g);
  for (const p of g.players)
    assert.equal(p.pos, E.gateCell(p, 2), 'every pawn returns to its succession-map gate');
  const south = g.players.find(p => p.gateId === 'P2');
  assert.equal(south.pos, '12,12', 'the south gate moves on the succession map');
  assert.equal(a.equipment.length, 6);
  assert.ok(a.prestige >= 2, 'kept the starting Prestige (guard rolls may add more)');
  const names = Object.values(g.factionSites).filter(Boolean).sort();
  assert.deepEqual(plain(names), ['army','elites','officials']);
  assert.equal(Object.keys(g.factionSites).length, 6);
  const gB = runToPhase2(mk());
  assert.deepEqual(plain(g.factionSites), plain(gB.factionSites), 'same seed deals the same factions');
}

// Searching card spaces and buying support at a revealed faction.
{
  const g = runToPhase2(mk());
  g.currentRoll = {dice:[4,4], total:8};
  const site = Object.keys(g.factionSites)[0];
  const a = E.active(g);
  a.pos = site; a.prestige = 2;
  assert.ok(find(g, 'search_site', x => x.dest === site));
  assert.ok(!find(g, 'gain_support'), 'nothing is for sale before the search');
  E.applyAction(g, find(g, 'search_site'));
  const faction = g.factionSites[site];
  if (faction) {
    const b = E.active(g);
    b.pos = site; b.prestige = 1; g.currentRoll = {dice:[2,2], total:4};
    const buy = find(g, 'gain_support', x => x.dest === site);
    assert.ok(buy, 'a revealed faction sells support');
    E.applyAction(g, buy);
    assert.deepEqual(plain(b.support), [faction]);
    assert.equal(b.prestige, 0);
  } else {
    assert.ok(!find(g, 'gain_support'), 'an empty street sells nothing');
  }
}

// Duel resolution with abilities: best single modifier, pugio tie-break.
// Street cells only: rows 0, 6, 12 and columns 0, 6, 12, 18 are open.
function duelCase({attacker, defender, dice, vsClaimant, checks}) {
  const g = mk();
  g.phase = 2; g.currentRoll = {dice:[6,6], total:12};
  const a = E.active(g);
  const d = g.players.find(p => p !== a);
  if (vsClaimant) {
    g.pendingClaim = {player:d.id, claimId:1, claim_id:1, round:g.round, responded:[]};
    a.prestige = 1;                        // the contest fee
  }
  a.equipment = attacker; d.equipment = defender;
  a.pos = '6,4'; d.pos = '6,8';            // column 6 street, four steps apart
  g.diceOverrides = {combat: dice};
  const act = find(g, 'duel', x => x.target === d.id);
  assert.ok(act, 'duel is legal within range');
  if (vsClaimant) assert.equal(act.contest_cost, 1, 'challenging the claimant costs the fee');
  const rec = E.applyAction(g, act);
  const ev = rec.events.find(e => e.type === 'duel');
  checks({g, rec, ev, a, d});
  return g;
}
duelCase({attacker:[], defender:['pugio'], dice:[3,3], checks:({ev,d}) => {
  assert.equal(ev.attacker_score, 3); assert.equal(ev.defender_score, 3);
  assert.equal(ev.winner, d.id, 'the lone pugio holder wins a tie');
}});
duelCase({attacker:['pugio'], defender:['pugio'], dice:[4,4], checks:({ev}) => {
  assert.equal(ev.winner, ev.attacker, 'both hold the pugio: the attacker wins');
}});
duelCase({attacker:[], defender:[], dice:[5,5], checks:({ev,a}) => {
  assert.equal(ev.winner, a.id, 'neither holds the pugio: the attacker wins the tie');
}});
duelCase({attacker:['gladius','pilum'], defender:[], dice:[2,2], vsClaimant:true, checks:({ev}) => {
  assert.equal(ev.attacker_bonus, 1, 'gladius and pilum against the claimant add +1, not +2');
}});
duelCase({attacker:['scutum'], defender:[], dice:[6,3], checks:({ev}) => {
  assert.equal(ev.attacker_bonus, 0, 'the scutum only helps the defender');
  assert.equal(ev.defender_bonus, 0);
}});
duelCase({attacker:[], defender:['scutum'], dice:[3,3], checks:({ev,d}) => {
  assert.equal(ev.defender_bonus, 1);
  assert.equal(ev.winner, d.id, 'the scutum turns a 3 vs 3 tie into a defender win by score');
}});
duelCase({attacker:['gladius','pugio'], defender:['scutum'], dice:[3,3], checks:({ev,a}) => {
  assert.equal(ev.attacker_bonus, 1, 'gladius and pugio combine: +1 plus the passive tie-break');
  assert.equal(ev.defender_bonus, 1);
  assert.equal(ev.winner, a.id, 'the tie goes to the lone pugio holder');
}});

// Contest fee, shame, and the lorica segmentata.
{
  const g = mk();
  g.phase = 2; g.currentRoll = {dice:[6,6], total:12};
  const a = E.active(g);
  const claimant = g.players.find(p => p !== a);
  g.pendingClaim = {player:claimant.id, claimId:1, claim_id:1, round:1, responded:[]};
  claimant.pos = '9,6'; claimant.support = ['army','elites'];
  claimant.equipment = ['lorica_segmentata'];
  a.pos = '6,8'; a.prestige = 1;
  g.diceOverrides = {combat:[6,1]};
  const act = find(g, 'duel', x => x.target === claimant.id);
  assert.equal(act.contest_cost, 1);
  E.applyAction(g, act);
  assert.equal(a.prestige, 1, 'fee paid before the roll, duel reward after');
  assert.equal(claimant.prestige, 0, 'shame never goes below zero');
  assert.ok(!g.pendingClaim, 'the claim dies');
  assert.equal(claimant.pos, '9,6', 'the unused lorica keeps the beaten claimant in place');
  assert.equal(claimant.abilitiesUsed.prevent_displacement, 'lorica_segmentata');
  // A second beaten claim (lorica spent) walks back to the gate.
  g.pendingClaim = {player:claimant.id, claimId:2, claim_id:2, round:2, responded:[]};
  g.currentRoll = {dice:[6,6], total:12};
  let a2 = E.active(g), guard2 = 0;
  while (a2 === claimant && guard2++ < 4) {   // the claimant just maintains
    E.applyAction(g, E.legalActions(g).find(x => x.kind === 'maintain_claim'));
    g.currentRoll = {dice:[6,6], total:12};
    a2 = E.active(g);
  }
  a2.pos = '6,8'; a2.prestige = 1;
  g.diceOverrides = {combat:[6,1]};
  const act2 = E.legalActions(g).find(x => x.kind==='duel' && x.target===claimant.id);
  assert.ok(act2 && act2.contest_cost === 1);
  E.applyAction(g, act2);
  assert.equal(claimant.pos, E.gateCell(claimant, 2), 'no lorica left: back to the gate');
}

// The claim window: two full rounds unchallenged crown the claimant.
{
  const g = runToPhase2(mk());
  g.currentRoll = {dice:[2,2], total:4};
  const claimant = E.active(g);
  claimant.pos = '9,6'; claimant.support = ['army','elites'];
  E.applyAction(g, find(g, 'proclaim'));
  const proclaimedRound = g.pendingClaim.round;
  let guard = 0;
  while (!g.winner && guard++ < 60) {
    g.currentRoll = {dice:[2,2], total:4};
    const acts = E.legalActions(g).filter(x => !(x.kind === 'duel' && x.target === claimant.id));
    if (E.active(g) === claimant) {
      E.applyAction(g, acts.find(x => x.kind === 'maintain_claim') ?? acts[0]);
    } else E.applyAction(g, acts[0]);
  }
  assert.equal(g.winner, claimant.id);
  assert.equal(g.endReason, 'survived_window');
  assert.ok(g.round - proclaimedRound >= 2);
}
{
  const g = runToPhase2(mk());
  g.currentRoll = {dice:[6,6], total:12};
  const claimant = E.active(g);
  claimant.pos = '9,6'; claimant.support = ['army','elites'];
  E.applyAction(g, find(g, 'proclaim'));
  assert.ok(g.pendingClaim);
  let guard3 = 0;
  while (E.active(g) !== claimant && guard3++ < 8) {
    g.currentRoll = {dice:[2,2], total:4};
    E.applyAction(g, E.legalActions(g).find(x => x.kind !== 'duel' || x.target !== claimant.id));
  }
  g.currentRoll = {dice:[2,2], total:4};
  const walkAway = E.legalActions(g).find(x => x.kind === 'move' && x.dest !== '9,6');
  E.applyAction(g, walkAway);
  assert.ok(!g.pendingClaim, 'leaving the Peristyle cancels the claim');
}

// Guard posts pay on both maps; the galea reveals a district once.
{
  const g = mk();
  g.currentRoll = {dice:[6,6], total:12};
  const a = E.active(g);
  a.pos = '6,3';                            // next to the palace-map post at 6,2
  const act = find(g, 'guard_post', x => x.dest === '6,2');
  assert.ok(act, 'palace-map posts pay in phase 1');
  g.diceOverrides = {combat:[4]};
  E.applyAction(g, act);
  assert.equal(a.prestige, 1);
  const g2 = runToPhase2(mk());
  g2.currentRoll = {dice:[6,6], total:12};
  const b = E.active(g2);
  b.pos = '0,4';                            // two steps from the map-2 post at 0,2
  const act2 = find(g2, 'guard_post', x => x.dest === '0,2');
  assert.ok(act2, 'succession-map posts pay in phase 2');
  const before2 = b.prestige;
  g2.diceOverrides = {combat:[3]};
  E.applyAction(g2, act2);
  assert.equal(b.prestige, before2, 'a roll under 4 earns nothing');
}
{
  const g = mk();
  g.currentRoll = {dice:[2,2], total:4};
  const a = E.active(g);
  a.equipment = ['galea'];
  const hidden = Object.keys(BOARD.map1.districts).filter(n => !(n in g.revealed));
  assert.ok(hidden.length);
  const act = find(g, 'inspect', x => x.district === hidden[0]);
  assert.ok(act, 'the galea may reveal any hidden district');
  E.applyAction(g, act);
  assert.equal(g.revealed[hidden[0]], g.districtEquipment[hidden[0]]);
  assert.equal(a.abilitiesUsed.reveal_district, 'galea');
  g.currentRoll = {dice:[2,2], total:4};
  assert.ok(!find(g, 'inspect'), 'the galea works once per game');
}
// Forty seeded bot games finish. Every seat runs a different strategy;
// each game must reach a winner or a timeout draw with sane Prestige.
{
  const ctx = vm.createContext({console, structuredClone});
  for (const f of ['board-data.js','engine.js','succession-engine.js','succession-bots.js'])
    vm.runInContext(readFileSync(new URL('web/'+f,root),'utf8'),ctx);
  const E2 = ctx.DIOCLET_ENGINE, BOTS = ctx.DIOCLET_BOTS;
  const kinds = ['greedy','aggressive','balanced','random'];
  const mulberry = s => () => {
    s = s + 0x6D2B79F5 | 0;
    let t = Math.imul(s ^ s >>> 15, 1 | s);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
  let botWins = 0;
  for (let n = 0; n < 40; n++) {
    const seed = 1000 + n;
    const seats = ['P0','P1','P2','P3'].map(id => ({id, name:id, kind:'human'}));
    const g = E2.newGame(seed, seats);
    const rng = mulberry(seed);
    let steps = 0;
    while (g.status !== 'finished' && steps++ < 3000) {
      const who = E2.active(g);
      const kind = kinds[(n + +who.id.slice(1)) % 4];
      E2.applyAction(g, BOTS.choose(kind, g, E2.legalActions(g), rng));
    }
    assert.equal(g.status, 'finished', `bot game seed ${seed} terminates`);
    assert.ok(g.winner || g.draw, 'a winner or a timeout draw');
    if (g.winner) botWins++;
    for (const p of g.players) {
      assert.ok(Number.isInteger(p.prestige) && p.prestige >= 0, 'integer Prestige, never negative');
      assert.ok(p.support.every(f => BOARD.succession.factionNames.includes(f)));
    }
  }
  assert.ok(botWins > 0, 'at least one crowned winner across the forty games');
}
console.log('succession engine invariants pass.');
