/* V0.8 succession rules. Legacy games keep the original engine. */
(function (global) {
  "use strict";
  const B = global.DIOCLET_BOARD;
  if (B.mode !== "succession-v1") return;
  const geometry = global.DIOCLET_ENGINE;
  const C = B.succession;
  const G = B.prestigeRules || { guard_post_success_min_roll: 4, guard_post_reward: 1,
    duel_win_reward: 1, first_challenger_reward: 1 };
  const combat = B.combatRules || {};
  const gearBonus = count => combat.equipment_bonus_tiers
    ? combat.equipment_bonus_tiers.find(t => count >= t.min_count && count <= t.max_count).bonus
    : geometry.gearBonus(count);
  const SALTS = { gates: 0xA5A5A5A5, order: 0x243F6A88,
    equipment: 0x9E3779B9, movement: 0xB7E15162, combat: 0xDEADBEEF,
    bots: 0x85EBCA6B };
  const distanceMaps = new Map();
  function distancesFrom(start) {
    if (!distanceMaps.has(start)) distanceMaps.set(start, geometry.distancesFrom(start));
    return distanceMaps.get(start);
  }
  const distance = (a, b) => distancesFrom(a).get(b);
  const key = c => c.join(",");
  const cap = () => B.gloryCap == null ? Infinity : B.gloryCap;
  const coordinate = value => typeof value === "string" ? value : key(value);
  const districtAt = Object.fromEntries(Object.entries(B.districts).map(([n, c]) => [key(c), n]));
  const factions = Object.keys(C.factions).sort();
  const factionCell = f => coordinate(C.factions[f]);
  function random(g, stream) {
    let x = g.rngStates[stream] >>> 0;
    x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
    g.rngStates[stream] = x >>> 0;
    return (x >>> 0) / 4294967296;
  }
  function die(g, stream) {
    const queued = g.diceOverrides?.[stream];
    if (queued?.length) {
      const value = queued.shift();
      if (!Number.isInteger(value) || value < 1 || value > B.movement.sides) throw Error("Invalid injected die");
      return value;
    }
    return 1 + Math.floor(random(g, stream) * B.movement.sides);
  }
  function shuffle(g, values, stream) {
    const out = values.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(random(g, stream) * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }
  function player(g, id) { return g.players.find(p => p.id === id); }
  function active(g) {
    // A terminal game retains the actor of its final completed turn.
    const id = (g.winner || g.draw) && g.events.length
      ? g.events[g.events.length - 1].player : g.order[g.turnIndex];
    return player(g, id);
  }
  function newGame(seed, seats, options = {}) {
    if (!Number.isSafeInteger(Number(seed))) throw Error("The seed must be an integer");
    if (seats.length !== 4 || new Set(seats.map(s => s.id)).size !== 4 ||
        seats.some(s => !Object.hasOwn(B.gates, s.id))) throw Error("Four distinct player IDs are required");
    const g = { mode: "succession-v1", seed: Number(seed), rngStates: {}, players: [],
      order: [], turnRoundStart: 0, turnIndex: 0, turnSeq: 0,
      phase: 1, round: 1, equipmentMap: {}, revealed: {},
      firstClaimer: null, claimRound: null, transitionAt: null,
      currentRoll: null, pendingClaim: null, winner: null, draw: false,
      log: [], events: [], phase1Timeout: false, phase2Timeout: false,
      roundsLevel1: null, policyVersion: "succession-bots-v080.1" };
    for (const [name, salt] of Object.entries(SALTS)) g.rngStates[name] = ((g.seed >>> 0) ^ salt) >>> 0 || 1;
    if (options.diceOverrides) g.diceOverrides = structuredClone(options.diceOverrides);
    g.rng = () => random(g, "bots");
    const ids = seats.map(s => s.id).sort();
    const mode = options.gateMode || C.gate_assignment || "random";
    let gates = ids.slice();
    const explicit = options.gateOrder || C.gate_order;
    if (explicit) {
      if (explicit.length !== 4 || new Set(explicit).size !== 4 || explicit.some(id => !ids.includes(id))) throw Error("Gate assignment must be a permutation");
      gates = explicit.slice();
    } else if (mode === "random") gates = shuffle(g, ids, "gates");
    else if (mode === "rotation") {
      const rotation = options.gateRotation ?? C.gate_rotation ?? 0;
      if (!Number.isInteger(rotation) || rotation < 0 || rotation > 3) throw Error("Gate rotation must be 0 to 3");
      gates = ids.map((_, i) => ids[(i + rotation) % 4]);
    } else if (mode !== "manual") throw Error("Unknown gate assignment mode");
    g.gateMode = mode;
    g.gateAssignment = Object.fromEntries(ids.map((id, i) => [id, gates[i]]));
    g.players = ids.map((id, i) => {
      const seat = seats.find(s => s.id === id), gateId = gates[i], gate = key(B.gates[gateId]);
      return { id, name: seat.name || id, kind: seat.kind || "human", index: i,
        gateId, gate, pos: gate, equipment: [], prestige: 0, support: [], turns: 0 };
    });
    g.order = shuffle(g, ids, "order");
    const equipment = shuffle(g, B.equipment, "equipment");
    Object.keys(B.districts).sort().forEach((n, i) => { g.equipmentMap[key(B.districts[n])] = equipment[i]; });
    startTurn(g);
    return g;
  }
  function startTurn(g) {
    if (g.winner || g.draw) return;
    const dice = Array.from({ length: B.movement.count }, () => die(g, "movement"));
    g.currentRoll = { dice, total: dice.reduce((a, b) => a + b, 0) };
    g.turnSeq++;
    active(g).turns++;
  }
  function event(rec, type, values = {}) { rec.events.push({ type, ...values }); }
  function nextTurn(g, rec) {
    g.turnIndex = (g.turnIndex + 1) % 4;
    const endRound = g.turnIndex === g.turnRoundStart;
    if (endRound) {
      g.round++;
      g.turnRoundStart = B.rotateFirst === false ? 0 : (g.turnRoundStart + 1) % 4;
      g.turnIndex = g.turnRoundStart;
      if (g.phase === 1 && (g.round > B.l1MaxRounds || (g.transitionAt !== null && g.round > g.transitionAt))) {
        g.roundsLevel1 = g.round - 1;
        g.phase1Timeout = g.firstClaimer === null;
        if (C.reset_positions) for (const p of g.players) p.pos = p.gate;
        g.phase = 2; g.round = 1; g.turnRoundStart = 0; g.turnIndex = 0;
        event(rec, "phase_transition", { from_phase: 1, to_phase: 2, auto_granted: {}, reset_positions: Boolean(C.reset_positions) });
        g.log.push("The succession begins. Equipment, support, and Prestige remain yours.");
      } else if (g.phase === 2 && g.round > B.l2MaxRounds) {
        g.draw = true; g.phase2Timeout = true; g.round = B.l2MaxRounds; g.currentRoll = null;
        event(rec, "game_draw", { reason: "phase2_timeout" });
        g.log.push("No claim prevails before the succession deadline. A draw.");
        return;
      }
    }
    startTurn(g);
  }
  function legalActions(g) {
    if (g.winner || g.draw) return [];
    const p = active(g), dist = distancesFrom(p.pos), actions = [];
    const add = (kind, dest, extra = {}) => actions.push({ kind, dest, dist: dist.get(dest), turnId: g.turnSeq, ...extra });
    const specials = dest => {
      if (Object.hasOwn(districtAt, dest)) {
        const revealed = g.revealed[dest];
        if (!revealed || !p.equipment.includes(revealed)) add("explore", dest);
      }
      if ((g.phase === 2 || C.support_in_city) && p.prestige >= C.support_cost) {
        for (const faction of factions) {
          if (dest === factionCell(faction) && !p.support.includes(faction)) add("gain_support", dest, { faction });
        }
      }
      if (g.phase === 1 && !g.firstClaimer && p.equipment.length === 6 && dest === key(B.checkpoint)) add("claim_checkpoint", dest);
      if (g.phase === 2 && dest === key(B.checkpoint)) {
        if (!g.pendingClaim && p.support.length >= C.required_support) add("proclaim", dest);
        if (g.pendingClaim?.claimant === p.id) add("maintain_claim", dest);
      }
    };
    for (const [dest, steps] of dist) {
      if (steps > g.currentRoll.total) continue;
      if (steps === 0) {
        if (B.movement.allowStationary !== false) specials(dest);
        else if (g.pendingClaim?.claimant === p.id && dest === key(B.checkpoint)) add("maintain_claim", dest);
        continue;
      }
      add("move", dest);
      specials(dest);
      if (B.gloryPosts.some(c => key(c) === dest) && p.prestige < cap()) add("guard_post", dest);
      for (const q of g.players) {
        if (q.id === p.id || distance(dest, q.pos) > B.movement.duelRange) continue;
        const contestCost = g.pendingClaim?.claimant === q.id ? (C.contest_cost || 0) : 0;
        if (p.prestige < contestCost) continue;
        add("duel", dest, { target: q.id, spend_prestige: false, spend: false, contest_cost: contestCost });
        if (p.prestige >= contestCost + C.challenge_cost) add("duel", dest, { target: q.id, spend_prestige: true, spend: true, contest_cost: contestCost });
      }
    }
    actions.sort((a, b) => {
      const [ax, ay] = a.dest.split(",").map(Number), [bx, by] = b.dest.split(",").map(Number);
      return a.kind.localeCompare(b.kind) || ax - bx || ay - by ||
        (a.target || "").localeCompare(b.target || "") || Number(Boolean(a.spend_prestige)) - Number(Boolean(b.spend_prestige)) ||
        (a.faction || "").localeCompare(b.faction || "");
    });
    return actions.map((a, i) => ({ ...a, action_id: "a" + String(i + 1).padStart(4, "0") }));
  }
  const actionFields = ["kind", "dest", "target", "spend_prestige", "faction", "turnId", "action_id", "contest_cost"];
  function sameAction(a, b) { return actionFields.every(k => a[k] === b[k]); }
  function grant(g, p, amount, rec, source) {
    const kept = Math.min(amount, cap() - p.prestige);
    p.prestige += kept;
    event(rec, "prestige_earned", { player: p.id, amount: kept, wasted: amount - kept, source });
    return kept;
  }
  function spend(p, amount, rec, purpose) {
    p.prestige -= amount;
    event(rec, "prestige_spent", { player: p.id, amount, purpose });
  }
  function cancelClaim(g, rec, reason) {
    if (!g.pendingClaim) return;
    event(rec, "claim_cancelled", { player: g.pendingClaim.claimant, claim_id: g.pendingClaim.id, reason });
    g.log.push(player(g, g.pendingClaim.claimant).name + " loses the claim: " + reason + ".");
    g.pendingClaim = null;
  }
  function applyAction(g, supplied) {
    const action = legalActions(g).find(a => sameAction(a, supplied));
    if (!action) throw Error("Illegal or stale action; refresh the current legal actions");
    const p = active(g), oldClaim = g.pendingClaim && { ...g.pendingClaim, responded: g.pendingClaim.responded.slice() };
    const rec = { player: p.id, kind: action.kind, dest: action.dest, turnId: g.turnSeq,
      phase: g.phase, round: g.round, action: { ...action }, dice: [], events: [], notes: [] };
    p.pos = action.dest;
    if (g.pendingClaim?.claimant === p.id && p.pos !== key(B.checkpoint)) cancelClaim(g, rec, "left the Peristyle");
    if (action.kind === "explore") {
      const item = g.equipmentMap[action.dest];
      if (!g.revealed[action.dest]) { g.revealed[action.dest] = item; event(rec, "treasure_revealed", { district: districtAt[action.dest], item }); }
      if (!p.equipment.includes(item)) {
        p.equipment.push(item);
        event(rec, "equipment_collected", { player: p.id, item });
        rec.notes.push("collected " + item);
      } else rec.notes.push("already owns this equipment");
    } else if (action.kind === "guard_post") {
      const roll = die(g, "combat"); rec.dice.push(roll);
      const success = roll >= G.guard_post_success_min_roll;
      event(rec, "guard_post", { player: p.id, roll, success });
      const kept = success ? grant(g, p, G.guard_post_reward, rec, "guard_post") : 0;
      rec.notes.push("guard duty " + roll + ": +" + kept + " Prestige");
    } else if (action.kind === "gain_support") {
      spend(p, C.support_cost, rec, "faction_support");
      p.support.push(action.faction);
      event(rec, "support_gained", { player: p.id, faction: action.faction });
      rec.notes.push("secured " + action.faction + " support");
    } else if (action.kind === "duel") {
      const q = player(g, action.target);
      if (action.contest_cost) spend(p, action.contest_cost, rec, "claim_contest");
      if (action.spend_prestige) spend(p, C.challenge_cost, rec, "challenge");
      const attackerDie = die(g, "combat"), defenderDie = die(g, "combat");
      rec.dice.push(attackerDie, defenderDie);
      const attack = attackerDie + gearBonus(p.equipment.length) + (action.spend_prestige ? C.challenge_bonus : 0);
      const defence = defenderDie + gearBonus(q.equipment.length);
      const winner = attack > defence || (attack === defence && !combat.tie_goes_to_defender) ? p : q;
      grant(g, winner, G.duel_win_reward, rec, "duel");
      event(rec, "duel", { attacker: p.id, defender: q.id, winner: winner.id,
        attacker_roll: attackerDie, defender_roll: defenderDie, attacker_total: attack, defender_total: defence,
        spend_prestige: action.spend_prestige });
      rec.notes.push("challenge " + attack + " vs " + defence + ": " + winner.name + " wins");
      if (winner.id === p.id && g.pendingClaim?.claimant === q.id) {
        cancelClaim(g, rec, "defeated by " + p.name);
        q.pos = q.gate;
        event(rec, "claimant_returned", { player: q.id, destination: q.gate });
      }
    } else if (action.kind === "claim_checkpoint") {
      g.firstClaimer = p.id; g.claimRound = g.round;
      g.transitionAt = Math.min(g.round + B.graceRounds, B.l1MaxRounds);
      grant(g, p, G.first_challenger_reward, rec, "first_challenger");
      event(rec, "first_challenger", { player: p.id, transition_at: g.transitionAt });
      rec.notes.push("opens the succession countdown");
    } else if (action.kind === "proclaim") {
      g.pendingClaim = { claimant: p.id, player: p.id, responded: [], id: g.turnSeq, claim_id: g.turnSeq };
      event(rec, "claim_proclaimed", { player: p.id, claim_id: g.turnSeq });
      rec.notes.push("claims imperial power; every rival gets a response");
    } else if (action.kind === "maintain_claim") rec.notes.push("maintains the claim");
    else rec.notes.push("moves to " + action.dest);
    if (oldClaim && g.pendingClaim?.id === oldClaim.id && p.id !== oldClaim.claimant && !g.pendingClaim.responded.includes(p.id)) {
      g.pendingClaim.responded.push(p.id);
      event(rec, "claim_response", { player: p.id, claim_id: oldClaim.id });
      if (g.pendingClaim.responded.length === 3) {
        g.winner = g.pendingClaim.claimant;
        event(rec, "game_won", { player: g.winner, reason: "claim_survived" });
        g.log.push(player(g, g.winner).name + " is acclaimed emperor.");
      }
    }
    g.log.push(p.name + ": " + rec.notes.join("; "));
    g.events.push(rec);
    if (!g.winner) nextTurn(g, rec);
    return rec;
  }
  global.DIOCLET_ENGINE = { ...geometry, newGame, legalActions, applyAction, player, active,
    distancesFrom, distance, gearBonus, mode: "succession-v1", version: "succession-engine-v080.1" };
})(typeof window !== "undefined" ? window : globalThis);
