/* Public-information strategies for the succession prototype. */
(function (global) {
  "use strict";
  const B = global.DIOCLET_BOARD;
  if (B.mode !== "succession-v1") return;
  const E = global.DIOCLET_ENGINE, C = B.succession;
  const VERSION = "succession-bots-v080.1";
  const cell = c => Array.isArray(c) ? c.join(",") : c;
  const byKind = (acts, kind) => acts.filter(a => a.kind === kind);
  const nearest = acts => acts.slice().sort((a, b) => a.dist - b.dist || a.action_id.localeCompare(b.action_id))[0];
  function publicView(g) {
    return {
      phase: g.phase, round: g.round, roll: g.currentRoll?.total,
      firstClaimer: g.firstClaimer,
      pendingClaim: g.pendingClaim && { claimant: g.pendingClaim.claimant, responded: g.pendingClaim.responded.slice() },
      revealed: { ...g.revealed },
      players: g.players.map(p => ({ id: p.id, pos: p.pos, gate: p.gate,
        equipment: p.equipment.slice(), support: p.support.slice(), prestige: p.prestige })),
      activeId: (g.activePlayer || E.active(g)).id,
    };
  }
  function toward(acts, target, desiredRange = 0) {
    const moves = byKind(acts, "move");
    return moves.slice().sort((a, b) =>
      Math.max(0, E.distance(a.dest, target) - desiredRange) - Math.max(0, E.distance(b.dest, target) - desiredRange) ||
      a.dist - b.dist || a.action_id.localeCompare(b.action_id))[0];
  }
  function closest(from, cells) {
    return cells.slice().sort((a, b) => E.distance(from, a) - E.distance(from, b) || a.localeCompare(b))[0];
  }
  function missingTreasure(view, p) {
    // Unknown cards remain equally unknown. Never inspect equipmentMap.
    const known = [], unknown = [];
    for (const c of Object.values(B.districts).map(cell)) {
      if (!Object.hasOwn(view.revealed, c)) unknown.push(c);
      else if (!p.equipment.includes(view.revealed[c])) known.push(c);
    }
    return closest(p.pos, known.length ? known : unknown);
  }
  function duelProbability(p, q, action) {
    const bonus = E.gearBonus(p.equipment.length) - E.gearBonus(q.equipment.length) +
      (action.spend_prestige ? C.challenge_bonus : 0);
    let wins = 0;
    for (let a = 1; a <= B.movement.sides; a++) for (let d = 1; d <= B.movement.sides; d++) if (a + bonus > d || (a + bonus === d && !B.combatRules?.tie_goes_to_defender)) wins++;
    return wins / B.movement.sides ** 2;
  }
  function bestDuel(duels, view, p, urgent = false) {
    return duels.slice().sort((a, b) => {
      const ap = duelProbability(p, view.players.find(q => q.id === a.target), a);
      const bp = duelProbability(p, view.players.find(q => q.id === b.target), b);
      // Outside a claim response, spending to earn the same currency is costly.
      const av = ap - (!urgent && a.spend_prestige ? 0.5 : 0);
      const bv = bp - (!urgent && b.spend_prestige ? 0.5 : 0);
      return bv - av || a.dist - b.dist || a.action_id.localeCompare(b.action_id);
    })[0];
  }
  function choose(kind, game, acts, rng = Math.random) {
    if (!acts.length) throw Error("The bot has no legal action");
    const view = publicView(game), p = view.players.find(q => q.id === view.activeId);
    const proclaim = byKind(acts, "proclaim");
    if (proclaim.length) return proclaim[0];
    const maintain = byKind(acts, "maintain_claim");
    if (maintain.length) return maintain[0];
    if (view.pendingClaim && view.pendingClaim.claimant !== p.id) {
      const target = view.players.find(q => q.id === view.pendingClaim.claimant);
      const challenges = byKind(acts, "duel").filter(a => a.target === target.id);
      if (challenges.length) return bestDuel(challenges, view, p, true);
      // An already completed response cannot rescue a claim by retreating.
      if (!view.pendingClaim.responded.includes(p.id)) {
        const approach = toward(acts, target.pos, B.movement.duelRange);
        if (approach) return approach;
      }
    }
    if (kind === "random") {
      const weights = { explore: 4, gain_support: 5, claim_checkpoint: 5,
        guard_post: 3, duel: 2, move: 1 };
      const groups = [...new Set(acts.map(a => a.kind))];
      let value = rng() * groups.reduce((sum, k) => sum + (weights[k] || 1), 0);
      const selected = groups.find(k => (value -= weights[k] || 1) <= 0) || groups.at(-1);
      const pool = byKind(acts, selected);
      return pool[Math.min(pool.length - 1, Math.floor(rng() * pool.length))];
    }
    const checkpoint = byKind(acts, "claim_checkpoint");
    if (checkpoint.length) return checkpoint[0];
    const support = byKind(acts, "gain_support");
    const explore = byKind(acts, "explore");
    const posts = byKind(acts, "guard_post");
    const duels = byKind(acts, "duel");
    const neededSupport = p.support.length < C.required_support;
    const treasuryGoal = neededSupport ? C.support_cost : C.challenge_cost;
    const canBank = B.gloryCap == null || p.prestige < B.gloryCap;
    const factionTargets = Object.keys(C.factions).filter(f => !p.support.includes(f)).map(f => cell(C.factions[f]));
    const supportTarget = closest(p.pos, factionTargets);
    const treasureTarget = missingTreasure(view, p);
    const postTarget = closest(p.pos, B.gloryPosts.map(cell));
    const safeDuel = bestDuel(duels, view, p);
    const goodDuel = safeDuel && duelProbability(p, view.players.find(q => q.id === safeDuel.target), safeDuel) >= 0.58;
    if (view.phase === 2 && !neededSupport) return toward(acts, cell(B.checkpoint)) || nearest(acts);
    if (kind === "greedy") {
      // Collector: finish the equipment set before buying political backing.
      if (p.equipment.length < 6 && explore.length) return nearest(explore);
      if (p.equipment.length < 6 && treasureTarget) return toward(acts, treasureTarget) || nearest(acts);
      if (support.length) return nearest(support);
      if (p.prestige < treasuryGoal) {
        if (posts.length) return nearest(posts);
        if (canBank && goodDuel) return safeDuel;
        return toward(acts, postTarget) || nearest(acts);
      }
      return toward(acts, neededSupport ? supportTarget : cell(B.checkpoint)) || nearest(acts);
    }
    if (kind === "aggressive") {
      // Fighter: build a small gear bonus, then earn Prestige through rivals.
      if (p.equipment.length < 3 && explore.length) return nearest(explore);
      if (support.length && neededSupport) return nearest(support);
      if (canBank && p.prestige < Math.max(2, treasuryGoal) && safeDuel) return safeDuel;
      if (posts.length && p.prestige < treasuryGoal) return nearest(posts);
      if (p.equipment.length < 3 && treasureTarget) return toward(acts, treasureTarget) || nearest(acts);
      if (p.prestige >= C.support_cost && neededSupport) return toward(acts, supportTarget) || nearest(acts);
      if (explore.length) return nearest(explore);
      if (treasureTarget) return toward(acts, treasureTarget) || nearest(acts);
      return toward(acts, postTarget) || nearest(acts);
    }
    // Balanced and tactical: prefer useful opportunities over fixed routes.
    if (support.length && neededSupport) return nearest(support);
    if (explore.length) return nearest(explore);
    if (p.prestige < treasuryGoal) {
      if (posts.length) return nearest(posts);
      if (canBank && goodDuel) return safeDuel;
    }
    const goals = [];
    if (treasureTarget && p.equipment.length < 6) goals.push({ cell: treasureTarget, weight: view.phase === 1 ? 1 : 0.7 });
    if (neededSupport && p.prestige >= C.support_cost && supportTarget) goals.push({ cell: supportTarget, weight: 1.3 });
    if (neededSupport && p.prestige < C.support_cost && postTarget) goals.push({ cell: postTarget, weight: 1 });
    if (!neededSupport && view.phase === 1 && p.equipment.length === 6) goals.push({ cell: cell(B.checkpoint), weight: 2 });
    if (!goals.length && postTarget) goals.push({ cell: postTarget, weight: 1 });
    goals.sort((a, b) => E.distance(p.pos, a.cell) / a.weight - E.distance(p.pos, b.cell) / b.weight || a.cell.localeCompare(b.cell));
    return toward(acts, goals[0]?.cell || cell(B.checkpoint)) || nearest(acts);
  }
  global.DIOCLET_BOTS = { choose, version: VERSION, publicView, duelProbability };
})(typeof window !== "undefined" ? window : globalThis);
