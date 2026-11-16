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

// The generated payload must describe the twin-board V0.10.2 game with
// exactly the printed-name keys: dead keys would keep dead engine
// branches alive, so the key sets are pinned exactly.
{
  assert.equal(B.rulesVersion, '0.10.2');
  assert.deepEqual(Object.keys(B).sort(),
    ['claimRequiredEquipment','combat','equipment','graceRounds','movement',
     'palaceMap','palaceMaxRounds','prestige','rotateFirst','rulesVersion',
     'startReveals','succession','successionMap','successionMaxRounds']);
  assert.deepEqual(Object.keys(B.succession).sort(),
    ['claimWindowRounds','contestFee','factionCells','factionNames',
     'gateAssignment','proclaimCost','requiredSupport','supportCost']);
  assert.deepEqual(Object.keys(B.prestige).sort(),
    ['cap','duelLoserCost','duelWinReward','guardMinRoll','guardReward']);
  assert.deepEqual(Object.keys(B.combat).sort(), ['abilities','tieGoesToDefender']);
  assert.equal(Object.keys(B.combat.abilities).length, 6);
  assert.equal(B.succession.claimWindowRounds, 2);
  assert.equal(B.succession.contestFee, 1);
  assert.equal(B.prestige.duelLoserCost, 1);
  assert.equal(B.startReveals, 2);
  assert.equal(B.claimRequiredEquipment, 6);
}

// Both maps: same street grid, different gates and Peristyle.
{
  assert.equal(B.palaceMap.width, 19); assert.equal(B.palaceMap.height, 13);
  assert.deepEqual(plain(B.palaceMap.blocked),
                   plain([...B.successionMap.blocked].sort((a,b)=>a[0]-b[0]||a[1]-b[1])));
  assert.deepEqual(plain(B.palaceMap.gates.P2), [6,12]);
  assert.deepEqual(plain(B.successionMap.gates.P2), [12,12], 'the south gate moves on the succession map');
  assert.deepEqual(plain(B.palaceMap.checkpoint), [6,6]);
  assert.deepEqual(plain(B.successionMap.checkpoint), [9,6]);
  assert.equal(B.successionMap.cardSpaces.length, 6);
  assert.equal(B.successionMap.guardPosts.length, 4);
  assert.equal(Object.keys(B.palaceMap.treasureEntries).length, 6);
  assert.equal(B.palaceMap.guardPosts.length, 4);
}

// Geometry: every cell reachable, pinwheel gates nine steps from the
// succession Peristyle, card spaces on streets, per-map caches.
{
  const dist1 = E.distancesFrom(key(B.palaceMap.gates.P0), E.MAPS.palace);
  assert.equal(dist1.size, 19*13 - B.palaceMap.blocked.length);
  const dist2 = E.distancesFrom(key(B.successionMap.checkpoint), E.MAPS.succession);
  for (const [id, cell] of Object.entries(B.successionMap.gates))
    assert.equal(dist2.get(key(cell)), 9, `gate ${id} nine steps from the succession Peristyle`);
  for (const site of B.successionMap.cardSpaces)
    assert.ok(!B.palaceMap.blocked.some(c => key(c) === key(site)), 'card spaces sit on streets');
  assert.notEqual(E.MAPS.palace.distanceMaps, E.MAPS.succession.distanceMaps);
  const p = E.path(key(B.palaceMap.gates.P0), key(B.palaceMap.checkpoint), E.MAPS.palace);
  assert.equal(p[0], key(B.palaceMap.gates.P0));
  assert.equal(p[p.length-1], key(B.palaceMap.checkpoint));
  assert.ok(p.every((k, i) => i === 0 || E.neighbors(p[i-1], E.MAPS.palace).includes(k)));
  assert.equal(E.cmp('a','b') < 0 && E.cmp('b','a') > 0 && E.cmp('a','a') === 0, true, 'codepoint compare');
}
console.log('board-data contract and geometry checks pass.');
