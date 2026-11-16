/* Public-information strategies for the V0.10.2 succession game.
 *
 * Bots choose only from the legal action list and never read hidden
 * state: the treasure mapping (districtEquipment) and the blind faction
 * deal (factionSites) are off limits - only revealed cards count. */
(function (global) {
  "use strict";
  const B = global.DIOCLET_BOARD;
  const E = global.DIOCLET_ENGINE, C = B.succession, ABIL = B.combat.abilities || {};
  const VERSION = "succession-bots-v0100.1";
  const byKind = (acts, kind) => acts.filter(a => a.kind === kind);
  const nearest = acts => acts.slice().sort((a, b) => a.dist - b.dist || cmpId(a, b))[0];
  const cmpId = (a, b) => (a.action_id < b.action_id ? -1 : a.action_id > b.action_id ? 1 : 0);
  function publicView(g) {
    return {
      phase: g.phase, round: g.round, roll: g.currentRoll?.total,
      firstClaimer: g.firstClaimer,
      pendingClaim: g.pendingClaim && { claimant: g.pendingClaim.player,
        responded: g.pendingClaim.responded.slice(), round: g.pendingClaim.round },
      revealed: { ...g.revealed },
      factionRevealed: g.factionSitesRevealed ? { ...g.factionSitesRevealed } : null,
      players: g.players.map(p => ({ id: p.id, pos: p.pos, gate: p.gate,
        equipment: p.equipment.slice(), support: p.support.slice(), prestige: p.prestige })),
      activeId: (g.activePlayer || E.active(g)).id,
    };
  }
  const dist = (g, a, b) => E.distance(a, b, E.mapFor(g).graph);
  function toward(g, acts, target, desiredRange = 0) {
    const moves = byKind(acts, "move");
    return moves.slice().sort((a, b) =>
      Math.max(0, dist(g, a.dest, target) - desiredRange) - Math.max(0, dist(g, b.dest, target) - desiredRange) ||
      a.dist - b.dist || cmpId(a, b))[0];
  }
  function closest(g, from, cells) {
    return cells.slice().sort((a, b) => dist(g, from, a) - dist(g, from, b) || (a < b ? -1 : a > b ? 1 : 0))[0];
  }
  const districtCells = Object.values(B.palaceMap.treasureEntries).map(c => c.join(","));
  const nameByCell = Object.fromEntries(Object.entries(B.palaceMap.treasureEntries).map(([n, c]) => [c.join(","), n]));
  function missingTreasure(view, p) {
    // Unknown cards remain equally unknown. Never read districtEquipment.
    const known = [], unknown = [];
    for (const c of districtCells) {
      const name = nameByCell[c];
      if (!Object.hasOwn(view.revealed, name)) unknown.push(c);
      else if (!p.equipment.includes(view.revealed[name])) known.push(c);
    }
    return closest(view._g, p.pos, known.length ? known : unknown);
  }
  /* Duel win probability with the V0.10.2 ability rules: one best
   * modifier per side, pugio breaks ties for its lone holder. */
  function duelProbability(p, q, action, claimantId) {
    const mods = (who, isAttack) => {
      const out = [];
      for (const item of who.equipment) {
        const spec = ABIL[item];
        if (!spec || spec.value <= 0) continue;
        if (isAttack && spec.type === "attack_bonus") out.push(spec.value);
        else if (isAttack && spec.type === "attack_vs_claimant" && claimantId === q.id) out.push(spec.value);
        else if (!isAttack && spec.type === "defense_bonus") out.push(spec.value);
      }
      return out.length ? Math.max(...out) : 0;
    };
    const diff = mods(p, true) - mods(q, false);
    const pPugio = p.equipment.some(i => ABIL[i]?.type === "win_ties");
    const qPugio = q.equipment.some(i => ABIL[i]?.type === "win_ties");
    let wins = 0;
    const sides = B.movement.sides;
    for (let a = 1; a <= sides; a++) for (let d = 1; d <= sides; d++) {
      if (a + diff > d) wins++;
      else if (a + diff === d && (pPugio !== qPugio ? pPugio : true)) wins++;
    }
    return wins / sides ** 2;
  }
  function bestDuel(g, duels, view, p) {
    const claimantId = view.pendingClaim?.claimant;
    return duels.slice().sort((a, b) => {
      const ap = duelProbability(p, view.players.find(q => q.id === a.target), a, claimantId);
      const bp = duelProbability(p, view.players.find(q => q.id === b.target), b, claimantId);
      const costA = a.contest_cost || 0, costB = b.contest_cost || 0;
      return (bp - costB * 0.4) - (ap - costA * 0.4) || a.dist - b.dist || cmpId(a, b);
    })[0];
  }
  function choose(kind, game, acts, rng = Math.random) {
    if (!acts.length) throw Error("The bot has no legal action");
    const view = publicView(game);
    view._g = game;   // geometry only; hidden state is never read
    const p = view.players.find(q => q.id === view.activeId);
    const g = game, M = E.mapFor(g);
    const checkpoint = M.checkpoint;
    const posts = M.posts;
    const proclaim = byKind(acts, "proclaim");
    if (proclaim.length) return proclaim[0];
    const maintain = byKind(acts, "maintain_claim");
    if (maintain.length) return maintain[0];
    if (view.pendingClaim && view.pendingClaim.claimant !== p.id) {
      // A claim stands for two full rounds: challenge or close in.
      const target = view.players.find(q => q.id === view.pendingClaim.claimant);
      const challenges = byKind(acts, "duel").filter(a => a.target === target.id && p.prestige >= (a.contest_cost || 0));
      if (challenges.length) return bestDuel(g, challenges, view, p);
      return toward(g, acts, target.pos, B.movement.duelRange) || nearest(acts);
    }
    if (kind === "random") {
      const weights = { explore: 4, search_site: 4, gain_support: 5, claim_checkpoint: 5,
        guard_post: 3, duel: 2, inspect: 1, move: 1 };
      const groups = [...new Set(acts.map(a => a.kind))];
      let value = rng() * groups.reduce((sum, k) => sum + (weights[k] || 1), 0);
      const selected = groups.find(k => (value -= weights[k] || 1) <= 0) || groups.at(-1);
      const pool = byKind(acts, selected);
      return pool[Math.min(pool.length - 1, Math.floor(rng() * pool.length))];
    }
    const checkpointClaim = byKind(acts, "claim_checkpoint");
    if (checkpointClaim.length) return checkpointClaim[0];
    const support = byKind(acts, "gain_support");
    const search = byKind(acts, "search_site");
    const explore = byKind(acts, "explore");
    const guard = byKind(acts, "guard_post");
    const duels = byKind(acts, "duel");
    const neededSupport = p.support.length < C.requiredSupport;
    const treasuryGoal = neededSupport ? C.supportCost : C.contestFee;
    const canBank = B.prestige.cap == null || p.prestige < B.prestige.cap;
    // Blind support: head for a revealed faction that is still needed,
    // else for the nearest unsearched card space.
    const supportTargets = view.factionRevealed
      ? Object.entries(view.factionRevealed).filter(([cell, f]) => f && !p.support.includes(f)).map(([cell]) => cell)
      : [];
    const supportTarget = supportTargets.length ? closest(g, p.pos, supportTargets) : null;
    const unsearched = view.factionRevealed
      ? B.successionMap.cardSpaces.map(c => c.join(",")).filter(cell => !Object.hasOwn(view.factionRevealed, cell))
      : [];
    const searchTarget = unsearched.length ? closest(g, p.pos, unsearched) : null;
    const treasureTarget = missingTreasure(view, p);
    const postTarget = posts.size ? closest(g, p.pos, [...posts]) : null;
    const claimantId = view.pendingClaim?.claimant;
    const safeDuel = bestDuel(g, duels, view, p);
    const goodDuel = safeDuel && duelProbability(p, view.players.find(q => q.id === safeDuel.target), safeDuel, claimantId) >= 0.58;
    if (view.phase === 2 && !neededSupport) return toward(g, acts, checkpoint) || nearest(acts);
    if (kind === "greedy") {
      // Collector: finish the equipment set, then buy the backing.
      if (view.phase === 1 && p.equipment.length < 6 && explore.length) return nearest(explore);
      if (view.phase === 1 && p.equipment.length < 6 && treasureTarget) return toward(g, acts, treasureTarget) || nearest(acts);
      if (support.length) return nearest(support);
      if (p.prestige < treasuryGoal) {
        if (guard.length) return nearest(guard);
        if (canBank && goodDuel) return safeDuel;
        return postTarget ? toward(g, acts, postTarget) || nearest(acts) : nearest(acts);
      }
      if (search.length) return nearest(search);
      const goal = neededSupport ? (supportTarget ?? searchTarget) : checkpoint;
      return goal ? toward(g, acts, goal) || nearest(acts) : nearest(acts);
    }
    if (kind === "aggressive") {
      // Fighter: a little gear, then Prestige through rivals and posts.
      if (view.phase === 1 && p.equipment.length < 3 && explore.length) return nearest(explore);
      if (support.length && neededSupport) return nearest(support);
      if (canBank && p.prestige < Math.max(2, treasuryGoal) && safeDuel) return safeDuel;
      if (guard.length && p.prestige < treasuryGoal) return nearest(guard);
      if (view.phase === 1 && p.equipment.length < 3 && treasureTarget) return toward(g, acts, treasureTarget) || nearest(acts);
      if (neededSupport && p.prestige >= C.supportCost && (supportTarget || searchTarget))
        return toward(g, acts, supportTarget ?? searchTarget) || nearest(acts);
      if (view.phase === 1 && explore.length) return nearest(explore);
      if (view.phase === 1 && treasureTarget) return toward(g, acts, treasureTarget) || nearest(acts);
      if (search.length) return nearest(search);
      return postTarget ? toward(g, acts, postTarget) || nearest(acts) : nearest(acts);
    }
    // Balanced: take useful opportunities, then weigh the goals.
    if (support.length && neededSupport) return nearest(support);
    if (view.phase === 1 && explore.length) return nearest(explore);
    if (search.length) return nearest(search);
    if (p.prestige < treasuryGoal) {
      if (guard.length) return nearest(guard);
      if (canBank && goodDuel) return safeDuel;
    }
    const goals = [];
    if (view.phase === 1 && treasureTarget && p.equipment.length < 6) goals.push({ cell: treasureTarget, weight: 1 });
    if (neededSupport && supportTarget && p.prestige >= C.supportCost) goals.push({ cell: supportTarget, weight: 1.3 });
    if (neededSupport && searchTarget) goals.push({ cell: searchTarget, weight: 1.1 });
    if (neededSupport && !supportTarget && !searchTarget && postTarget) goals.push({ cell: postTarget, weight: 1 });
    if (!neededSupport && view.phase === 2) goals.push({ cell: checkpoint, weight: 2 });
    if (!goals.length && postTarget) goals.push({ cell: postTarget, weight: 1 });
    goals.sort((a, b) => dist(g, p.pos, a.cell) / a.weight - dist(g, p.pos, b.cell) / b.weight || (a.cell < b.cell ? -1 : 1));
    return goals.length ? toward(g, acts, goals[0].cell) || nearest(acts) : nearest(acts);
  }
  global.DIOCLET_BOTS = { choose, version: VERSION, publicView, duelProbability };
})(typeof window !== "undefined" ? window : globalThis);
