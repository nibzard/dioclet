/* Imperial Rivals: 305 AD - the V0.10.2 succession engine.
 *
 * A faithful port of the Python reference (engine.py driving
 * rules/imperial-rivals-v0.10.2.json): two maps that share one street
 * grid, six equipment abilities (best single modifier per duel side,
 * pugio tie-break), blind faction cards on the succession map, and a
 * two-full-round claim window. State field names mirror the Python
 * engine so the parity harness (tools/test_succession_parity.mjs) can
 * replay identical seeds against both implementations.
 */
(function (global) {
  "use strict";
  const B = global.DIOCLET_BOARD;
  const geo = global.DIOCLET_ENGINE;
  const C = B.succession;
  const PR = B.prestige;
  const ABIL = B.combat.abilities || {};
  const SALTS = { gates: 0xA5A5A5A5, order: 0x243F6A88,
    equipment: 0x9E3779B9, movement: 0xB7E15162, combat: 0xDEADBEEF,
    bots: 0x85EBCA6B };
  const key = c => c.join(",");
  const cmp = geo.cmp;
  const cap = () => PR.cap == null ? Infinity : PR.cap;

  const PALACE = {
    graph: geo.MAPS.palace,
    checkpoint: key(B.palaceMap.checkpoint),
    posts: new Set(B.palaceMap.guardPosts.map(key)),
    gateCell: id => key(B.palaceMap.gates[id]),
  };
  const SUCCESSION = {
    graph: geo.MAPS.succession,
    checkpoint: key(B.successionMap.checkpoint),
    posts: new Set(B.successionMap.guardPosts.map(key)),
    cardSpaces: B.successionMap.cardSpaces,
    gateCell: id => key(B.successionMap.gates[id]),
  };
  const mapFor = g => (g.phase === 1 ? PALACE : SUCCESSION);
  const gateCell = (p, phase) => (phase === 1 ? PALACE : SUCCESSION).gateCell(p.gateId);

  const districtAt = Object.fromEntries(Object.entries(B.palaceMap.treasureEntries).map(([n, c]) => [key(c), n]));
  const districtNames = Object.keys(B.palaceMap.treasureEntries).sort(cmp);
  const factionNames = C.factionNames.slice().sort(cmp);
  const factionCell = f => key(C.factionCells[f]);

  function distancesFrom(start, graph) { return geo.distancesFrom(start, graph); }
  const distanceIn = (g, a, b) => geo.distance(a, b, mapFor(g).graph);

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
  /* Best-one-never-sum helpers, mirroring _usable_ability/_ability_total. */
  function usableAbility(p, type) {
    for (const item of p.equipment) {
      const spec = ABIL[item];
      if (spec && spec.type === type && spec.value > 0 && !p.abilitiesUsed[type]) return item;
    }
    return null;
  }
  function abilityTotal(p, type) {
    let total = 0;
    for (const item of p.equipment) {
      const spec = ABIL[item];
      if (spec && spec.type === type) total += spec.value;
    }
    return total;
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
        seats.some(s => !Object.hasOwn(B.palaceMap.gates, s.id))) throw Error("Four distinct player IDs are required");
    const g = { seed: Number(seed), rngStates: {}, players: [],
      order: [], turnRoundStart: 0, turnIndex: 0, turnSeq: 0,
      phase: 1, round: 1, districtEquipment: {}, revealed: {}, setupReveals: [],
      firstClaimer: null, triggerRound: null, transitionAt: null,
      currentRoll: null, pendingClaim: null, winner: null, draw: false,
      endReason: null, status: "in_progress",
      factionSites: null, factionSitesRevealed: null,
      equipmentAtTransition: {},
      palaceTimeout: false, successionTimeout: false, roundsPalace: null,
      log: [], events: [], policyVersion: "succession-engine-v0100.1" };
    for (const [name, salt] of Object.entries(SALTS)) g.rngStates[name] = ((g.seed >>> 0) ^ salt) >>> 0 || 1;
    if (options.diceOverrides) g.diceOverrides = structuredClone(options.diceOverrides);
    g.rng = () => random(g, "bots");
    const ids = seats.map(s => s.id).sort(cmp);
    const assignment = options.gateMode || C.gateAssignment || "random";
    let gates = ids.slice();
    const explicit = options.gateOrder;
    if (explicit) {
      if (explicit.length !== 4 || new Set(explicit).size !== 4 || explicit.some(id => !ids.includes(id))) throw Error("Gate assignment must be a permutation");
      gates = explicit.slice();
    } else if (assignment === "random") gates = shuffle(g, ids, "gates");
    else if (assignment === "rotation") {
      const rotation = options.gateRotation ?? 0;
      if (!Number.isInteger(rotation) || rotation < 0 || rotation > 3) throw Error("Gate rotation must be 0 to 3");
      gates = ids.map((_, i) => ids[(i + rotation) % 4]);
    } else if (assignment !== "manual") throw Error("Unknown gate assignment mode");
    g.gateMode = assignment;
    g.gateAssignment = Object.fromEntries(ids.map((id, i) => [id, gates[i]]));
    g.players = ids.map((id, i) => {
      const seat = seats.find(s => s.id === id), gateId = gates[i], gate = PALACE.gateCell(gateId);
      return { id, name: seat.name || id, kind: seat.kind || "human", index: i,
        gateId, gate, pos: gate, equipment: [], prestige: 0, support: [],
        turns: 0, abilitiesUsed: {} };
    });
    g.order = shuffle(g, ids, "order");
    const equipment = shuffle(g, B.equipment, "equipment");
    districtNames.forEach((n, i) => { g.districtEquipment[n] = equipment[i]; });
    if (B.startReveals) {
      for (const name of shuffle(g, districtNames, "equipment").slice(0, B.startReveals)) {
        g.revealed[name] = g.districtEquipment[name];
      }
      g.setupReveals = Object.keys(g.revealed).sort(cmp);
    }
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
    event(rec, "claim_cancelled", { player: g.pendingClaim.player, claim_id: g.pendingClaim.claimId, reason });
    g.log.push(player(g, g.pendingClaim.player).name + " loses the claim: " + reason + ".");
    g.pendingClaim = null;
  }

  /* Turn advance, mirroring _advance: on the round wrap check the claim
   * window first, then the phase-1 transition or the phase-2 deadline.
   * Terminal paths return before startTurn, so no dice are rolled. */
  function advance(g, rec) {
    if (g.winner || g.draw) return;
    g.turnIndex = (g.turnIndex + 1) % 4;
    if (g.turnIndex === g.turnRoundStart) {
      g.round++;
      g.turnRoundStart = B.rotateFirst === false ? 0 : (g.turnRoundStart + 1) % 4;
      g.turnIndex = g.turnRoundStart;
      const window = C.claimWindowRounds;
      const pending = g.pendingClaim;
      if (window && g.phase === 2 && pending && g.round - pending.round > window) {
        g.winner = pending.player; g.status = "finished"; g.endReason = "survived_window";
        event(rec, "game_won", { player: pending.player, cause: "survived_window" });
        g.log.push(player(g, pending.player).name + " holds the claim through the window and is emperor.");
        g.currentRoll = null;
        return;
      }
      if (g.phase === 1 && (g.round > B.palaceMaxRounds ||
          (g.transitionAt !== null && g.round > g.transitionAt))) {
        g.roundsPalace = g.round - 1;
        g.palaceTimeout = g.firstClaimer === null;
        g.equipmentAtTransition = Object.fromEntries(g.players.map(p => [p.id, p.equipment.length]));
        // Twin-board change: the succession map takes over and every seat
        // returns to its gate on that map.
        g.phase = 2;
        for (const p of g.players) p.pos = gateCell(p, 2);
        const floor = C.transitionMinPrestige || 0;
        if (floor > 0) {
          for (const p of g.players) {
            if (p.prestige < floor) grant(g, p, floor - p.prestige, rec, "phase_transition");
          }
        }
        g.round = 1; g.turnRoundStart = 0; g.turnIndex = 0;
        const cells = SUCCESSION.cardSpaces.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]).map(key);
        g.factionSites = {};
        cells.forEach(k => { g.factionSites[k] = null; });
        shuffle(g, cells, "order").slice(0, 3)
          .forEach((k, i) => { g.factionSites[k] = factionNames[i]; });
        g.factionSitesRevealed = {};
        event(rec, "phase_transition", { from_phase: 1, to_phase: 2, palace_timeout: g.palaceTimeout });
        g.log.push("The succession map takes over. Every pawn returns to its gate; items, Prestige, and support remain yours.");
      } else if (g.phase === 2 && g.round > B.successionMaxRounds) {
        // An engine backstop for a stalled game, not a printed rule: the
        // printed game ends only by a standing claim (D58).
        g.draw = true; g.successionTimeout = true; g.status = "finished"; g.endReason = "succession_timeout";
        g.round = B.successionMaxRounds; g.currentRoll = null;
        event(rec, "game_draw", { reason: "succession_timeout" });
        g.log.push("No claim prevails before the succession deadline. A draw.");
        return;
      }
    }
    startTurn(g);
  }

  function legalActions(g) {
    if (g.winner || g.draw) return [];
    const p = active(g), M = mapFor(g), dist = distancesFrom(p.pos, M.graph);
    const actions = [];
    const add = (kind, dest, extra = {}) => actions.push({ kind, dest, dist: dist.get(dest), turnId: g.turnSeq, ...extra });
    const specials = dest => {
      // Treasure entries exist only on the palace map; in phase 2 the
      // active board has no districts and explore is never offered.
      const district = g.phase === 1 ? districtAt[dest] : undefined;
      if (district !== undefined &&
          (!(district in g.revealed) || !p.equipment.includes(g.districtEquipment[district]))) add("explore", dest);
      if (g.phase === 2) {
        if (g.factionSites) {
          // Search unrevealed cells; buy support only at revealed factions.
          if (dest in g.factionSites && !(dest in g.factionSitesRevealed)) add("search_site", dest);
          const revealed = g.factionSitesRevealed?.[dest];
          if (revealed && !p.support.includes(revealed) && p.prestige >= C.supportCost) add("gain_support", dest, { faction: revealed });
        } else {
          for (const faction of factionNames) {
            if (dest === factionCell(faction) && !p.support.includes(faction) && p.prestige >= C.supportCost) add("gain_support", dest, { faction });
          }
        }
      }
      if (dest === M.checkpoint) {
        if (g.phase === 1 && g.firstClaimer === null && p.equipment.length >= B.claimRequiredEquipment) add("claim_checkpoint", dest);
        if (g.phase === 2 && !g.pendingClaim && p.support.length >= C.requiredSupport && p.prestige >= C.proclaimCost) add("proclaim", dest);
      }
    };
    for (const [dest, steps] of dist) {
      if (steps > g.currentRoll.total) continue;
      if (steps === 0) {
        if (B.movement.allowStationary !== false) specials(dest);
        continue;
      }
      add("move", dest);
      specials(dest);
      if (M.posts.has(dest) && p.prestige < cap()) add("guard_post", dest);
      for (const q of g.players) {
        if (q.id === p.id) continue;
        const dd = distanceIn(g, dest, q.pos);
        if (dd == null || dd > B.movement.duelRange) continue;
        const contestCost = g.pendingClaim?.player === q.id ? C.contestFee : 0;
        if (p.prestige < contestCost) continue;
        add("duel", dest, { target: q.id, spend_prestige: false, contest_cost: contestCost });
      }
    }
    // Helmet (galea): stationary, once-per-game public reveal of any hidden
    // treasure card (phase 1) or hidden faction card space (phase 2).
    if (B.movement.allowStationary !== false && usableAbility(p, "reveal_district")) {
      if (g.phase === 1) {
        for (const name of districtNames) {
          if (!(name in g.revealed)) add("inspect", p.pos, { district: name });
        }
      } else if (g.phase === 2 && g.factionSites) {
        for (const siteKey of Object.keys(g.factionSites).sort(cmp)) {
          if (!(siteKey in g.factionSitesRevealed)) add("inspect", p.pos, { site: siteKey });
        }
      }
    }
    if (g.pendingClaim?.player === p.id && p.pos === M.checkpoint) add("maintain_claim", p.pos);
    actions.sort((a, b) => {
      const [ax, ay] = a.dest.split(",").map(Number), [bx, by] = b.dest.split(",").map(Number);
      return cmp(a.kind, b.kind) || ax - bx || ay - by ||
        cmp(a.target || "", b.target || "") || Number(Boolean(a.spend_prestige)) - Number(Boolean(b.spend_prestige)) ||
        cmp(a.faction || "", b.faction || "") || cmp(a.district || "", b.district || "") || cmp(a.site || "", b.site || "");
    });
    return actions.map((a, i) => ({ ...a, action_id: "a" + String(i + 1).padStart(4, "0") }));
  }

  const actionFields = ["kind", "dest", "target", "spend_prestige", "faction", "district", "site", "turnId", "action_id", "contest_cost"];
  function sameAction(a, b) { return actionFields.every(k => a[k] === b[k]); }

  function applyAction(g, supplied) {
    const action = legalActions(g).find(a => sameAction(a, supplied));
    if (!action) throw Error("Illegal or stale action; refresh the current legal actions");
    const p = active(g), M = mapFor(g);
    const pendingBefore = g.pendingClaim && { ...g.pendingClaim, responded: g.pendingClaim.responded.slice() };
    const rec = { player: p.id, kind: action.kind, dest: action.dest, turnId: g.turnSeq,
      phase: g.phase, round: g.round, action: { ...action }, dice: [], events: [], notes: [] };
    p.pos = action.dest;
    if (g.pendingClaim?.player === p.id && p.pos !== M.checkpoint) cancelClaim(g, rec, "left_peristyle");

    if (action.kind === "explore") {
      const district = districtAt[action.dest];
      const item = g.districtEquipment[district];
      if (!(district in g.revealed)) {
        g.revealed[district] = item;
        event(rec, "district_revealed", { district, item });
      }
      if (!p.equipment.includes(item)) {
        p.equipment.push(item);
        event(rec, "equipment_collected", { player: p.id, district, item });
        rec.notes.push("collected " + item);
      } else rec.notes.push("already owns this equipment");
    } else if (action.kind === "inspect") {
      const item = usableAbility(p, "reveal_district");
      p.abilitiesUsed.reveal_district = item;
      if (action.site) {
        const faction = g.factionSites[action.site];
        g.factionSitesRevealed[action.site] = faction;
        event(rec, "support_site_revealed", { player: p.id, cell: action.site.split(",").map(Number), faction });
        event(rec, "ability_used", { player: p.id, ability: item, site: action.site });
        rec.notes.push("the helmet reveals card space " + action.site + ": " + (faction || "empty street"));
      } else {
        const district = action.district;
        g.revealed[district] = g.districtEquipment[district];
        event(rec, "district_revealed", { district, item: g.districtEquipment[district] });
        event(rec, "ability_used", { player: p.id, ability: item, district });
        rec.notes.push("the helmet reveals district " + district + ": " + g.districtEquipment[district]);
      }
    } else if (action.kind === "guard_post") {
      const roll = die(g, "combat"); rec.dice.push(roll);
      const success = roll >= PR.guardMinRoll;
      event(rec, "guard_post", { player: p.id, roll, success });
      const kept = success ? grant(g, p, PR.guardReward, rec, "guard_post") : 0;
      rec.notes.push("guard duty " + roll + ": +" + kept + " Prestige");
    } else if (action.kind === "search_site") {
      const faction = g.factionSites[action.dest];
      g.factionSitesRevealed[action.dest] = faction;
      event(rec, "support_site_revealed", { player: p.id, cell: action.dest.split(",").map(Number), faction });
      rec.notes.push(faction ? "the " + faction + " meet here" : "an empty street");
    } else if (action.kind === "gain_support") {
      spend(p, C.supportCost, rec, "faction_support");
      p.support.push(action.faction);
      p.support.sort(cmp);
      event(rec, "support_gained", { player: p.id, faction: action.faction });
      rec.notes.push("secured " + action.faction + " support");
    } else if (action.kind === "claim_checkpoint") {
      g.firstClaimer = p.id;
      g.triggerRound = g.round;
      g.transitionAt = Math.min(g.round + B.graceRounds, B.palaceMaxRounds);
      event(rec, "first_challenger", { player: p.id, transition_at: g.transitionAt });
      rec.notes.push("claims the checkpoint; the succession countdown begins");
    } else if (action.kind === "proclaim") {
      g.pendingClaim = { player: p.id, claimId: g.turnSeq, claim_id: g.turnSeq,
        round: g.round, responded: [] };
      if (C.proclaimCost) spend(p, C.proclaimCost, rec, "proclaim");
      event(rec, "claim_proclaimed", { player: p.id, claim_id: g.turnSeq });
      rec.notes.push("proclaims a claim to the throne");
    } else if (action.kind === "maintain_claim") {
      event(rec, "claim_maintained", { player: p.id });
      rec.notes.push("maintains the claim");
    } else if (action.kind === "duel") {
      const q = player(g, action.target);
      if (action.contest_cost) spend(p, action.contest_cost, rec, "claim_contest");
      const attackRoll = die(g, "combat"), defenseRoll = die(g, "combat");
      rec.dice.push(attackRoll, defenseRoll);
      // At most one equipment modifier applies per side: the best one,
      // never the sum. The pilum counts only against the standing claimant.
      const attackMods = [], defenseMods = [];
      for (const item of p.equipment) {
        const spec = ABIL[item];
        if (!spec || spec.value <= 0) continue;
        if (spec.type === "attack_bonus") attackMods.push(spec.value);
        else if (spec.type === "attack_vs_claimant" && g.pendingClaim && g.pendingClaim.player === q.id) attackMods.push(spec.value);
      }
      for (const item of q.equipment) {
        const spec = ABIL[item];
        if (spec && spec.type === "defense_bonus" && spec.value > 0) defenseMods.push(spec.value);
      }
      const attackBonus = attackMods.length ? Math.max(...attackMods) : 0;
      const defenseBonus = defenseMods.length ? Math.max(...defenseMods) : 0;
      const attackScore = attackRoll + attackBonus, defenseScore = defenseRoll + defenseBonus;
      // Pugio: the lone holder wins a tied duel; if both or neither hold
      // one, the base tie rule decides.
      const attackerPugio = abilityTotal(p, "win_ties") > 0;
      const defenderPugio = abilityTotal(q, "win_ties") > 0;
      let won;
      if (attackScore !== defenseScore) won = attackScore > defenseScore;
      else if (attackerPugio !== defenderPugio) {
        won = attackerPugio;
        const holder = won ? p : q;
        event(rec, "ability_used", { player: holder.id,
          ability: holder.equipment.find(i => ABIL[i]?.type === "win_ties") });
      } else won = !B.combat.tieGoesToDefender;
      const winner = won ? p : q;
      event(rec, "duel", { attacker: p.id, defender: q.id, winner: winner.id,
        attacker_roll: attackRoll, defender_roll: defenseRoll,
        attacker_bonus: attackBonus, defender_bonus: defenseBonus,
        attacker_score: attackScore, defender_score: defenseScore,
        spend_prestige: Boolean(action.spend_prestige) });
      grant(g, winner, PR.duelWinReward, rec, "duel");
      const shame = PR.duelLoserCost ?? 0;
      if (shame) {
        const loser = won ? q : p;
        const paid = Math.min(shame, loser.prestige);
        if (paid) spend(loser, paid, rec, "duel_shame");
      }
      rec.notes.push("duel " + attackScore + " vs " + defenseScore + ": " + winner.name + " wins");
      if (won && g.pendingClaim && g.pendingClaim.player === q.id) {
        cancelClaim(g, rec, "challenge_won");
        // Lorica: once per game the beaten claimant keeps their position.
        // The claim still dies; only the walk back to the gate is saved.
        const loricaItem = usableAbility(q, "prevent_displacement");
        if (loricaItem) {
          q.abilitiesUsed.prevent_displacement = loricaItem;
          event(rec, "ability_used", { player: q.id, ability: loricaItem });
        } else {
          q.pos = gateCell(q, g.phase);
          event(rec, "claimant_returned", { player: q.id, destination: q.pos });
        }
      }
    } else rec.notes.push("moves to " + action.dest);

    // Response bookkeeping survives for the record; under a claim window
    // mere responses no longer crown anyone - the window decides.
    const pending = g.pendingClaim;
    if (pendingBefore && pending && pending.claimId === pendingBefore.claimId && p.id !== pendingBefore.player) {
      if (!pending.responded.includes(p.id)) {
        pending.responded.push(p.id);
        event(rec, "claim_response", { player: p.id, claim_id: pending.claimId });
      }
    }
    g.log.push(p.name + ": " + rec.notes.join("; "));
    g.events.push(rec);
    if (!g.winner && !g.draw) advance(g, rec);
    return rec;
  }

  global.DIOCLET_ENGINE = { ...geo, mapFor, gateCell, newGame, legalActions, applyAction,
    player, active, distanceIn, usableAbility, abilityTotal,
    version: "succession-engine-v0100.1" };
})(typeof window !== "undefined" ? window : globalThis);
