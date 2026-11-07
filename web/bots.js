/* Bot players for the web board: ports of the repository's frozen
 * V0.1 policies (policies.py, D24) plus the versioned balanced_se
 * probe (D32). They choose only from the legal action list, exactly
 * like their Python counterparts, including the northwest
 * destination tie-break. */
(function (global) {
  "use strict";

  const B = global.DIOCLET_BOARD;

  function byKind(acts, kind) { return acts.filter(a => a.kind === kind); }
  function destKey(a) { const [x, y] = a.dest.split(",").map(Number); return [x, y]; }
  function dist(a) { return a.dist; }
  function nearest(acts) {
    return acts.reduce((best, a) => {
      const ka = [dist(a), destKey(a)], kb = [dist(best), destKey(best)];
      return ka[0] < kb[0] || (ka[0] === kb[0] &&
        (ka[1][0] < kb[1][0] || (ka[1][0] === kb[1][0] && ka[1][1] < kb[1][1])))
        ? a : best;
    });
  }
  function manhattan(a, b) {
    const [ax, ay] = a.split(",").map(Number), [bx, by] = b.split(",").map(Number);
    return Math.abs(ax - bx) + Math.abs(ay - by);
  }
  function bestMoveToward(acts, target) {
    const moves = byKind(acts, "move");
    if (!moves.length) return null;
    return moves.reduce((best, a) => {
      const ka = [manhattan(a.dest, target), destKey(a)];
      const kb = [manhattan(best.dest, target), destKey(best)];
      return ka[0] < kb[0] || (ka[0] === kb[0] &&
        (ka[1][0] < kb[1][0] || (ka[1][0] === kb[1][0] && ka[1][1] < kb[1][1])))
        ? a : best;
    });
  }

  function level1Target(g, p) {
    const mine = new Set(p.equipment);
    const known = [], unknown = [];
    for (const [cellk, item] of Object.entries(g.revealed)) {
      if (!mine.has(item)) known.push(cellk);
    }
    for (const n of Object.keys(B.districts)) {
      const cellk = B.districts[n].join(",");
      if (!(cellk in g.revealed)) unknown.push(cellk);
    }
    for (const pool of [known, unknown]) {
      if (pool.length) {
        return pool.reduce((best, c) => {
          const ka = [manhattan(p.pos, c), c.split(",").map(Number)];
          const kb = [manhattan(p.pos, best), best.split(",").map(Number)];
          return ka[0] < kb[0] || (ka[0] === kb[0] &&
            (ka[1][0] < kb[1][0] || (ka[1][0] === kb[1][0] && ka[1][1] < kb[1][1])))
            ? c : best;
        });
      }
    }
    return null;
  }

  function level2Target(g, p) {
    const lacking = ["cellars", "guard_barracks", "peristyle"]
      .filter(s => !p.seals.includes(s));
    if (lacking.length && p.seals.length < B.sealsRequired) {
      return lacking.map(s => B.level2[s].join(","))
        .reduce((best, c) => manhattan(p.pos, c) < manhattan(p.pos, best) ? c : best);
    }
    return B.level2.emperor.join(",");
  }

  function pickDuel(g, p, acts) {
    const duels = byKind(acts, "duel");
    if (!duels.length) return null;
    if (p.glory >= B.gloryCap) return null;
    return duels.reduce((best, a) => {
      const q = g.players.find(x => x.id === a.target);
      const ka = [q.equipment.length, destKey(a)];
      const qb = g.players.find(x => x.id === best.target);
      const kb = [qb.equipment.length, destKey(best)];
      return ka[0] < kb[0] || (ka[0] === kb[0] &&
        (ka[1][0] < kb[1][0] || (ka[1][0] === kb[1][0] && ka[1][1] < kb[1][1])))
        ? a : best;
    });
  }

  const randomWeights = { claim_checkpoint: 4, explore: 3, attempt_seal: 3,
                          attack_emperor: 3, duel: 2, guard_post: 2, move: 1 };

  function choose(kind, g, acts, rng) {
    const p = g.activePlayer;
    if (kind === "random") {
      const kinds = [...new Set(acts.map(a => a.kind))];
      let total = 0;
      const w = kinds.map(k => { total += randomWeights[k] || 1;
                                 return randomWeights[k] || 1; });
      let r = rng() * total, picked = kinds[0];
      for (let i = 0; i < kinds.length; i++) { r -= w[i]; if (r <= 0) { picked = kinds[i]; break; } }
      const pool = byKind(acts, picked);
      return pool[Math.floor(rng() * pool.length)];
    }
    if (kind === "greedy") {
      if (g.phase === 1) {
        const claim = byKind(acts, "claim_checkpoint");
        if (claim.length) return claim[0];
        const explores = byKind(acts, "explore");
        if (explores.length) return nearest(explores);
        const t = level1Target(g, p) || B.checkpoint.join(",");
        return bestMoveToward(acts, t) || nearest(byKind(acts, "move"));
      }
      const atk = byKind(acts, "attack_emperor");
      if (atk.length) return atk.find(a => !a.spend) || atk[0];
      const seals = byKind(acts, "attempt_seal");
      if (seals.length) return nearest(seals);
      return bestMoveToward(acts, level2Target(g, p)) || nearest(byKind(acts, "move"));
    }
    if (kind === "aggressive") {
      const duel = pickDuel(g, p, acts);
      if (duel) return duel;
      if (g.phase === 1) {
        const claim = byKind(acts, "claim_checkpoint");
        if (claim.length) return claim[0];
        const explores = byKind(acts, "explore");
        if (explores.length) return nearest(explores);
        const t = level1Target(g, p) || B.checkpoint.join(",");
        return bestMoveToward(acts, t) || nearest(byKind(acts, "move"));
      }
      const atk = byKind(acts, "attack_emperor");
      if (atk.length) return atk.find(a => a.spend) || atk[0];
      const seals = byKind(acts, "attempt_seal");
      if (seals.length) {
        const spenders = seals.filter(a => a.spend);
        return spenders.length ? spenders[0] : nearest(seals);
      }
      return bestMoveToward(acts, level2Target(g, p)) || nearest(byKind(acts, "move"));
    }
    // balanced (and balanced_se uses the same logic; ties differ only
    // in direction, which this port does not need for play)
    if (g.phase === 1) {
      const claim = byKind(acts, "claim_checkpoint");
      if (claim.length) return claim[0];
      const explores = byKind(acts, "explore");
      if (explores.length) return nearest(explores);
      const posts = byKind(acts, "guard_post");
      if (posts.length && p.glory < B.gloryCap) return nearest(posts);
      const duel = pickDuel(g, p, acts);
      if (duel) return duel;
      const t = level1Target(g, p) ||
        B.gloryPosts.map(c => c.join(","))
          .reduce((b, c) => manhattan(p.pos, c) < manhattan(p.pos, b) ? c : b);
      return bestMoveToward(acts, t) || nearest(byKind(acts, "move"));
    }
    const atk = byKind(acts, "attack_emperor");
    if (atk.length) {
      const spend = atk.find(a => a.spend === (p.glory >= B.gloryCap));
      return spend || atk[0];
    }
    const seals = byKind(acts, "attempt_seal");
    if (seals.length) {
      const spenders = seals.filter(a => a.spend);
      if (spenders.length && p.glory >= B.gloryCap) return spenders[0];
      return nearest(seals);
    }
    return bestMoveToward(acts, level2Target(g, p)) || nearest(byKind(acts, "move"));
  }

  global.DIOCLET_BOTS = { choose };
})(typeof window !== "undefined" ? window : globalThis);
