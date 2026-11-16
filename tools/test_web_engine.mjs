// Board-data contract and shared geometry checks for the V0.10.2 web kit.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const root = new URL('../', import.meta.url);
const ctx = vm.createContext({console,structuredClone});
vm.runInContext(readFileSync(new URL('web/board-data.js',root),'utf8'),ctx);
vm.runInContext(readFileSync(new URL('web/engine.js',root),'utf8'),ctx);
const B = ctx.DIOCLET_BOARD, E = ctx.DIOCLET_ENGINE;
const key = c => c.join(',');
const plain = v => JSON.parse(JSON.stringify(v));

// The generated payload must describe the twin-board V0.10.2 game and
// must not carry any field from the retired V0.8 shape: dead keys would
// keep dead engine branches alive.
{
  assert.equal(B.mode, 'succession-v1');
  assert.equal(B.rulesVersion, '0.10.2');
  for (const gone of ['level2','sealsRequired','hitsToWin','prestigeRules','combatRules','gloryCap','districts','blocked','gates','checkpoint','gloryPosts'])
    assert.ok(!Object.hasOwn(B, gone), `legacy top-level key ${gone} must be gone`);
  assert.ok(!('support_in_city' in B.succession) && !('factions' in B.succession) && !('reset_positions' in B.succession));
  assert.equal(Object.keys(B.combat.abilities).length, 6);
  assert.equal(B.succession.blindSupport, true);
  assert.equal(B.succession.claimWindowRounds, 2);
  assert.equal(B.succession.contestCost, 1);
  assert.equal(B.glory.duelLoserCost, 1);
  assert.equal(B.startReveals, 2);
  assert.equal(B.claimRequiredEquipment, 6);
  assert.equal(B.succession.challengeBonus, 0, 'the paid boost is gone in 0.10.2');
}

// Both maps: same street grid, different gates and Peristyle.
{
  assert.equal(B.map1.width, 19); assert.equal(B.map1.height, 13);
  assert.deepEqual(plain(B.map1.blocked),
                   plain([...B.boardLevel2.blocked].sort((a,b)=>a[0]-b[0]||a[1]-b[1])));
  assert.deepEqual(plain(B.map1.gates.P2), [6,12]);
  assert.deepEqual(plain(B.boardLevel2.gates.P2), [12,12], 'the south gate moves on the succession map');
  assert.deepEqual(plain(B.map1.checkpoint), [6,6]);
  assert.deepEqual(plain(B.boardLevel2.checkpoint), [9,6]);
  assert.equal(B.boardLevel2.supportSites.length, 6);
  assert.equal(B.boardLevel2.gloryPosts.length, 4);
}

// Geometry: every cell reachable, pinwheel gates nine steps from the
// succession Peristyle, card spaces on streets, per-map caches.
{
  const dist1 = E.distancesFrom(key(B.map1.gates.P0), E.MAPS.map1);
  assert.equal(dist1.size, 19*13 - B.map1.blocked.length);
  const dist2 = E.distancesFrom(key(B.boardLevel2.checkpoint), E.MAPS.map2);
  for (const [id, cell] of Object.entries(B.boardLevel2.gates))
    assert.equal(dist2.get(key(cell)), 9, `gate ${id} nine steps from the succession Peristyle`);
  for (const site of B.boardLevel2.supportSites)
    assert.ok(!B.map1.blocked.some(c => key(c) === key(site)), 'card spaces sit on streets');
  assert.notEqual(E.MAPS.map1.distanceMaps, E.MAPS.map2.distanceMaps);
  const p = E.path(key(B.map1.gates.P0), key(B.map1.checkpoint), E.MAPS.map1);
  assert.equal(p[0], key(B.map1.gates.P0));
  assert.equal(p[p.length-1], key(B.map1.checkpoint));
  assert.ok(p.every((k, i) => i === 0 || E.neighbors(p[i-1], E.MAPS.map1).includes(k)));
  assert.equal(E.cmp('a','b') < 0 && E.cmp('b','a') > 0 && E.cmp('a','a') === 0, true, 'codepoint compare');
}
console.log('board-data contract and geometry checks pass.');
