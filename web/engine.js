/* Diocletian's Palace web engine.
 *
 * A port of the repository's Python engine for the adopted real-board
 * ruleset (rules_v06_realboard_p3.json, decisions D1-D31): 107 street
 * spaces, blocked buildings, 2d6 movement, single-die trials, duels
 * with attacker ties, Glory cap 2, grace 1, rotating first player,
 * city cap 24, two seals then two Emperor hits.
 *
 * The module is environment agnostic: it runs in the browser and in
 * Node for the logic tests (tools/test_web_engine.mjs).
 */
(function (global) {
  "use strict";

  const B = global.DIOCLET_BOARD;
  const DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]]; // N, E, S, W tie-break

  // Mulberry32: small, fast, seedable, good enough for game dice.
  function makeRng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function d6(rng) { return 1 + Math.floor(rng() * 6); }

  function key(x, y) { return x + "," + y; }
  function cell(k) { return k.split(",").map(Number); }

  function buildBoard() {
    const blocked = new Set(B.blocked.map(([x, y]) => key(x, y)));
    const walkable = [];
    for (let y = 0; y < B.height; y++) {
      for (let x = 0; x < B.width; x++) {
        if (!blocked.has(key(x, y))) walkable.push(key(x, y));
      }
    }
    return { blocked, walkable };
  }
  const BOARD = buildBoard();

  function neighbors(k) {
    const [x, y] = cell(k);
    const out = [];
    for (const [dx, dy] of DIRS) {
      const nx = x + dx, ny = y + dy;
      if (nx >= 0 && nx < B.width && ny >= 0 && ny < B.height &&
          !BOARD.blocked.has(key(nx, ny))) out.push(key(nx, ny));
    }
    return out;
  }

  function distancesFrom(start) {
    const dist = new Map([[start, 0]]);
    const queue = [start];
    while (queue.length) {
      const cur = queue.shift();
      for (const n of neighbors(cur)) {
        if (!dist.has(n)) { dist.set(n, dist.get(cur) + 1); queue.push(n); }
      }
    }
    return dist;
  }

  /* Deterministic path: walk toward the destination taking the first
   * neighbor (N, E, S, W) that reduces the distance, as in board.py. */
  function path(start, dest) {
    if (start === dest) return [start];
    const distTo = distancesFrom(dest);
    const path = [start];
    let cur = start;
    while (cur !== dest) {
      for (const n of neighbors(cur)) {
        if ((distTo.get(n) ?? distTo.get(cur) + 1) < distTo.get(cur)) {
          cur = n; break;
        }
      }
      path.push(cur);
    }
    return path;
  }

  function distance(a, b) {
    if (a === b) return 0;
    return distancesFrom(b).get(a);
  }

  function gearBonus(count) {
    if (count >= 6) return 2;
    if (count >= 3) return 1;
    return 0;
  }

  /* ------------------------------------------------------------------ */

  function newGame(seed, seats) {
    // seats: [{id, kind, name}] kind in human|balanced|greedy|aggressive|random
    const rng = makeRng(seed);
    const players = seats.map((s, i) => ({
      id: s.id, name: s.name, kind: s.kind,
      gate: key(...B.gates[s.id]),
      pos: key(...B.gates[s.id]),
      glory: 0, equipment: [], seals: [], hits: 0, turns: 0,
      index: i,
    }));
    // Shuffle the turn order from the seed (D5), then rotate the
    // starting seat every round (adopted V0.2 rule).
    const ids = players.map(p => p.id);
    for (let i = ids.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [ids[i], ids[j]] = [ids[j], ids[i]];
    }
    const order = ids;
    // Hidden equipment mapping, shuffled from the same seed.
    const equip = B.equipment.slice();
    for (let i = equip.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [equip[i], equip[j]] = [equip[j], equip[i]];
    }
    const districtNames = Object.keys(B.districts);
    const equipmentMap = {};
    districtNames.forEach((n, i) => {
      equipmentMap[key(...B.districts[n])] = equip[i];
    });
    const g = {
      seed, rng, players, order, turnRoundStart: 0,
      phase: 1, round: 1, turnIndex: 0, turnSeq: 0,
      equipmentMap, revealed: {},
      firstClaimer: null, claimRound: null, transitionAt: null,
      currentRoll: null, winner: null, draw: false,
      log: [],
    };
    nextTurn(g, true);
    return g;
  }

  const DISTRICT_AT = {};
  for (const n of Object.keys(B.districts)) DISTRICT_AT[key(...B.districts[n])] = n;

  function player(g, id) { return g.players.find(p => p.id === id); }
  function active(g) { return player(g, g.order[g.turnIndex]); }

  function nextTurn(g, first) {
    if (g.winner || g.draw) return;
    // Advance the seat pointer.
    if (!first) {
      g.turnIndex = (g.turnIndex + 1) % 4;
      if (g.turnIndex === g.turnRoundStart) {
        endRound(g);
        if (g.winner || g.draw) return;
      }
    }
    // City-phase transition checks happen on round boundaries.
    if (g.phase === 1 && g.transitionAt !== null && g.round > g.transitionAt) {
      enterLevel2(g);
      if (g.winner || g.draw) return;
    }
    if (g.phase === 1 && g.round > B.l1MaxRounds) { enterLevel2(g); }
    if (g.phase === 2 && g.round > B.l2MaxRounds) {
      g.draw = true; g.log.push("The palace gates close: the game is a draw.");
      return;
    }
    const rolls = [];
    for (let i = 0; i < B.movement.count; i++) rolls.push(d6(g.rng));
    g.currentRoll = { dice: rolls, total: rolls.reduce((a, b) => a + b, 0) };
    active(g).turns += 1;
    g.turnSeq += 1;
  }

  function endRound(g) {
    g.round += 1;
    // Rotate the first player (adopted rule).
    g.turnRoundStart = (g.turnRoundStart + 1) % 4;
    g.turnIndex = g.turnRoundStart;
  }

  function enterLevel2(g) {
    const granted = [];
    for (const p of g.players) {
      for (const it of B.equipment) {
        if (!p.equipment.includes(it)) {
          p.equipment.push(it); granted.push(p.id + ":" + it);
        }
      }
      p.pos = p.gate;
    }
    g.phase = 2; g.round = 1;
    g.turnRoundStart = 0; g.turnIndex = 0;
    g.log.push("The gate opens. Everyone enters the palace" +
               (granted.length ? " (missing gear granted)" : "") + ".");
  }

  /* Legal actions ---------------------------------------------------- */

  function legalActions(g) {
    const p = active(g);
    const roll = g.currentRoll.total;
    const dist = distancesFrom(p.pos);
    const acts = [];
    const add = (kind, dest, extra) => acts.push(
      Object.assign({ kind, dest, dist: dist.get(dest) }, extra));

    for (const [k, d] of dist) {
      if (d === 0 || d > roll) continue;
      add("move", k);
      if (g.phase === 1) {
        if (DISTRICT_AT[k] !== undefined) {
          const item = g.equipmentMap[k];
          if (!p.equipment.includes(item)) add("explore", k, { item });
        }
        if (B.gloryPosts.some(c => key(...c) === k) && p.glory < B.gloryCap) {
          add("guard_post", k);
        }
      } else {
        for (const site of ["cellars", "guard_barracks", "peristyle"]) {
          if (key(...B.level2[site]) === k && !p.seals.includes(site)) {
            if (site === "peristyle" && p.glory >= 1) {
              add("attempt_seal", k, { site, spend: true });
            }
            add("attempt_seal", k, { site, spend: false });
          }
        }
        if (key(...B.level2.emperor) === k &&
            p.seals.length >= B.sealsRequired) {
          if (p.glory >= 1) add("attack_emperor", k, { spend: true });
          add("attack_emperor", k, { spend: false });
        }
      }
      // Duels: any target within duel range of the destination.
      for (const q of g.players) {
        if (q.id === p.id) continue;
        const dd = distance(k, q.pos);
        if (dd !== null && dd <= B.movement.duelRange) {
          add("duel", k, { target: q.id });
        }
      }
    }
    // Stationary specials (zero-step) where the rules allow them.
    if (g.phase === 1) {
      const k = p.pos;
      if (Object.values(B.districts).some(c => key(...c) === k)) {
        const item = g.equipmentMap[k];
        if (!p.equipment.includes(item)) add("explore", k, { dist: 0, item });
      }
      if (key(...B.checkpoint) === k && p.equipment.length === 6 &&
          !g.firstClaimer) add("claim_checkpoint", k, { dist: 0 });
    } else {
      const k = p.pos;
      for (const site of ["cellars", "guard_barracks", "peristyle"]) {
        if (key(...B.level2[site]) === k && !p.seals.includes(site)) {
          if (site === "peristyle" && p.glory >= 1)
            add("attempt_seal", k, { site, spend: true, dist: 0 });
          add("attempt_seal", k, { site, spend: false, dist: 0 });
        }
      }
      if (key(...B.level2.emperor) === k &&
          p.seals.length >= B.sealsRequired) {
        if (p.glory >= 1) add("attack_emperor", k, { spend: true, dist: 0 });
        add("attack_emperor", k, { spend: false, dist: 0 });
      }
    }
    // Claim while passing through or standing on the checkpoint.
    if (g.phase === 1 && !g.firstClaimer && p.equipment.length === 6) {
      const k = key(...B.checkpoint);
      const d = dist.get(k);
      if (d >= 1 && d <= roll) add("claim_checkpoint", k, { dist: d });
    }
    return acts;
  }

  function grantGlory(g, p, n) {
    const before = p.glory;
    p.glory = Math.min(B.gloryCap, p.glory + n);
    return p.glory - before;
  }

  /* Apply one legal action. Returns the record for the UI. -------- */
  function applyAction(g, action) {
    const p = active(g);
    const rec = { player: p.id, kind: action.kind, dest: action.dest,
                  dice: [], notes: [] };
    p.pos = action.dest;

    if (action.kind === "explore") {
      const item = g.equipmentMap[action.dest];
      if (!g.revealed[action.dest]) {
        g.revealed[action.dest] = item;
        rec.notes.push("revealed " + item);
      }
      if (!p.equipment.includes(item)) {
        p.equipment.push(item);
        rec.notes.push("collected " + item);
      } else {
        rec.notes.push("nothing new here");
      }
    } else if (action.kind === "guard_post") {
      const r = d6(g.rng); rec.dice.push(r);
      if (r >= 4) {
        const got = grantGlory(g, p, 1);
        rec.notes.push("guard post roll " + r + ": +" + got + " Glory");
      } else rec.notes.push("guard post roll " + r + ": no Glory");
    } else if (action.kind === "duel") {
      const q = player(g, action.target);
      const mine = d6(g.rng) + gearBonus(p.equipment.length);
      const theirs = d6(g.rng) + gearBonus(q.equipment.length);
      rec.dice.push(mine, theirs);
      if (mine >= theirs) { // attacker wins ties (adopted V0.2 rule)
        const got = grantGlory(g, p, 1);
        rec.notes.push("duel won " + mine + " vs " + theirs +
                       (got ? ", +1 Glory" : ", Glory already full"));
      } else {
        const got = grantGlory(g, q, 1);
        rec.notes.push("duel lost " + mine + " vs " + theirs +
                       (got ? ", defender +1 Glory" : ""));
      }
    } else if (action.kind === "claim_checkpoint") {
      g.firstClaimer = p.id;
      const got = grantGlory(g, p, 1);
      g.claimRound = g.round;
      g.transitionAt = Math.min(g.round + B.graceRounds, B.l1MaxRounds);
      rec.notes.push("first through the gate" + (got ? ", +1 Glory" : ""));
    } else if (action.kind === "attempt_seal") {
      const site = action.site;
      if (site === "peristyle" && action.spend) {
        p.glory -= 1;
        p.seals.push(site);
        rec.notes.push("bought the Peristyle seal for 1 Glory");
      } else if (site === "cellars") {
        const r = d6(g.rng); rec.dice.push(r);
        if (r >= 3) { p.seals.push(site); rec.notes.push("cellars roll " + r + ": seal"); }
        else rec.notes.push("cellars roll " + r + ": no seal");
      } else if (site === "guard_barracks") {
        const mine = d6(g.rng) + gearBonus(p.equipment.length);
        const guard = d6(g.rng) + 1;
        rec.dice.push(mine, guard);
        if (mine > guard) { p.seals.push(site); rec.notes.push("beat the guard " + mine + " vs " + guard + ": seal"); }
        else rec.notes.push("guard won " + guard + " vs " + mine);
      } else { // peristyle roll
        const r = d6(g.rng); rec.dice.push(r);
        if (r >= 5) { p.seals.push(site); rec.notes.push("peristyle roll " + r + ": seal"); }
        else rec.notes.push("peristyle roll " + r + ": no seal");
      }
    } else if (action.kind === "attack_emperor") {
      if (action.spend) p.glory -= 1;
      const mine = d6(g.rng) + gearBonus(p.equipment.length) +
                   (action.spend ? 2 : 0);
      const emperor = d6(g.rng) + 2;
      rec.dice.push(mine, emperor);
      if (mine > emperor) {
        p.hits += 1;
        rec.notes.push("HIT " + mine + " vs " + emperor +
                       " (" + p.hits + "/" + B.hitsToWin + ")");
        if (p.hits >= B.hitsToWin) {
          g.winner = p.id;
          rec.notes.push(p.name + " wins");
          g.log.push(p.name + " defeats the Emperor.");
          return rec;
        }
      } else {
        p.pos = key(...B.level2.retreat);
        rec.notes.push("miss " + mine + " vs " + emperor + ", retreat");
      }
    }
    g.log.push(rec.player + " " + rec.kind + ": " + rec.notes.join("; "));
    nextTurn(g);
    return rec;
  }

  const api = {
    newGame, legalActions, applyAction, player, active,
    distance, path, gearBonus, neighbors, distancesFrom,
  };
  global.DIOCLET_ENGINE = api;
})(typeof window !== "undefined" ? window : globalThis);
