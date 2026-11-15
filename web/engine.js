/* Imperial Rivals: 305 AD - shared board utilities for the web engine.
 *
 * The V0.10.2 game is played on two maps that share one street grid:
 * the palace map and the succession map (same blocked cells, different
 * gates, Peristyle, guard posts, and card spaces). This module owns the
 * per-map geometry: neighbor walks, breadth-first distances, and the
 * deterministic N-E-S-W path, each cached per map. All game rules live
 * in succession-engine.js, which mirrors the Python reference
 * (succession.py, rules_v0102_bigboard.json).
 *
 * The module is environment agnostic: it runs in the browser and in
 * Node for the logic tests (tools/test_web_engine.mjs).
 */
(function (global) {
  "use strict";

  const B = global.DIOCLET_BOARD;
  const DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]]; // N, E, S, W tie-break

  function key(x, y) { return x + "," + y; }
  function cell(k) { return k.split(",").map(Number); }

  function makeGraph(section) {
    const blocked = new Set(section.blocked.map(([x, y]) => key(x, y)));
    return { width: section.width, height: section.height, blocked,
             distanceMaps: new Map() };
  }
  const MAPS = {
    map1: makeGraph(B.map1),
    map2: makeGraph(B.boardLevel2),
  };

  function neighbors(k, graph) {
    const [x, y] = cell(k);
    const out = [];
    for (const [dx, dy] of DIRS) {
      const nx = x + dx, ny = y + dy;
      if (nx >= 0 && nx < graph.width && ny >= 0 && ny < graph.height &&
          !graph.blocked.has(key(nx, ny))) out.push(key(nx, ny));
    }
    return out;
  }

  function distancesFrom(start, graph) {
    if (!graph.distanceMaps.has(start)) {
      const dist = new Map([[start, 0]]);
      const queue = [start];
      while (queue.length) {
        const cur = queue.shift();
        for (const n of neighbors(cur, graph)) {
          if (!dist.has(n)) { dist.set(n, dist.get(cur) + 1); queue.push(n); }
        }
      }
      graph.distanceMaps.set(start, dist);
    }
    return graph.distanceMaps.get(start);
  }

  /* Deterministic path: walk toward the destination taking the first
   * neighbor (N, E, S, W) that reduces the distance, as in board.py. */
  function path(start, dest, graph) {
    if (start === dest) return [start];
    const distTo = distancesFrom(dest, graph);
    const path = [start];
    let cur = start;
    while (cur !== dest) {
      for (const n of neighbors(cur, graph)) {
        if ((distTo.get(n) ?? distTo.get(cur) + 1) < distTo.get(cur)) {
          cur = n; break;
        }
      }
      path.push(cur);
    }
    return path;
  }

  function distance(a, b, graph) {
    if (a === b) return 0;
    return distancesFrom(b, graph).get(a) ?? null;
  }

  /* Codepoint comparison: Python sorts strings by codepoint, and the
   * legal-action ordering must match the reference engine exactly.
   * localeCompare depends on the ICU build and must not be used. */
  function cmp(a, b) { return a < b ? -1 : a > b ? 1 : 0; }

  global.DIOCLET_ENGINE = {
    MAPS, key, cell, neighbors, distancesFrom, path, distance, cmp,
  };
})(typeof window !== "undefined" ? window : globalThis);
