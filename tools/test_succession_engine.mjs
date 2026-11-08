// Behavioral tests for the V0.8 browser engine and public strategies.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = name => readFileSync(new URL('../web/' + name, import.meta.url), 'utf8');
const context = vm.createContext({ console, structuredClone });
vm.runInContext(source('board-data.js'), context);
const B = context.DIOCLET_BOARD;
B.mode = 'succession-v1'; B.gloryCap = 3;
B.succession = { support_cost: 1, required_support: 2, support_in_city: true,
  challenge_cost: 1, challenge_bonus: 2, reset_positions: false, gate_assignment: 'random',
  factions: { army: [15, 12], officials: [6, 6], elites: [3, 0] } };
for (const name of ['engine.js', 'bots.js', 'succession-engine.js', 'succession-bots.js']) vm.runInContext(source(name), context);
const E = context.DIOCLET_ENGINE, BOT = context.DIOCLET_BOTS;
const seats = ['P0','P1','P2','P3'].map(id => ({id, name:id, kind:'human'}));
const plain = value => JSON.parse(JSON.stringify(value));
function test(name, fn) { fn(); console.log('  ok:', name); }
function game(seed = 2026) {
  const g = E.newGame(seed, seats, {gateMode:'manual'});
  g.order = ['P0','P1','P2','P3']; g.turnIndex = 0; g.turnRoundStart = 0;
  g.currentRoll = {dice:[3,3], total:6}; return g;
}
function take(g, kind, extra = {}) {
  const a = E.legalActions(g).find(a => a.kind === kind && Object.entries(extra).every(([k,v]) => a[k] === v));
  assert.ok(a, `missing action ${kind} ${JSON.stringify(extra)}`);
  return E.applyAction(g, a);
}
function move(g) { return take(g, 'move'); }
function claimingGame() {
  const g = game(); g.phase=2;
  const p=E.active(g); p.pos=B.checkpoint.join(','); p.support=['army','elites'];
  return g;
}
test('new-game gates are reproducible permutations and preserve player identities', () => {
  const a=E.newGame(481,seats), b=E.newGame(481,seats);
  assert.deepEqual(plain(a.gateAssignment),plain(b.gateAssignment));
  assert.equal(new Set(a.players.map(p=>p.gateId)).size,4);
  for(const p of a.players) assert.equal(p.name,p.id);
});
test('gate shuffle does not change order, treasures, or movement', () => {
  const a=E.newGame(81,seats,{gateMode:'manual'}),b=E.newGame(81,seats,{gateMode:'random'});
  assert.deepEqual(plain(a.order),plain(b.order));
  assert.deepEqual(plain(a.equipmentMap),plain(b.equipmentMap));
  assert.deepEqual(plain(a.currentRoll),plain(b.currentRoll));
});
test('four-session rotation uses every gate once', () => {
  const all=Array.from({length:4},(_,gateRotation)=>E.newGame(9,seats,{gateMode:'rotation',gateRotation}));
  for(const id of ['P0','P1','P2','P3']) assert.equal(new Set(all.map(g=>E.player(g,id).gateId)).size,4);
  assert.throws(()=>E.newGame(9,seats,{gateOrder:['P0','P0','P2','P3']}));
});
test('unopened treasure actions and public bot view do not reveal hidden cards', () => {
  const g=game(); E.active(g).pos=B.districts.A.join(',');
  assert.ok(E.legalActions(g).filter(a=>a.kind==='explore').every(a=>!Object.hasOwn(a,'item')));
  const view=BOT.publicView(g);
  assert.ok(!Object.hasOwn(view,'equipmentMap'));
  assert.ok(!JSON.stringify(view).includes('rngStates'));
});
test('collection remains legal in succession and never grants duplicates', () => {
  const g=game();g.phase=2;const p=E.active(g);p.pos=B.districts.A.join(',');
  take(g,'explore',{dest:p.pos});assert.equal(p.equipment.length,1);
  g.turnIndex=g.order.indexOf(p.id);g.currentRoll={dice:[1,1],total:2};
  assert.ok(!E.legalActions(g).some(a=>a.kind==='explore'&&a.dest===p.pos));
});
test('support is deterministic, costs Prestige, and cannot repeat', () => {
  const g=game(),p=E.active(g);p.pos=B.succession.factions.army.join(',');p.prestige=2;
  take(g,'gain_support',{faction:'army'});
  assert.equal(p.prestige,1);assert.deepEqual(plain(p.support),['army']);
  g.turnIndex=0;assert.ok(!E.legalActions(g).some(a=>a.kind==='gain_support'&&a.faction==='army'));
  p.prestige=0;p.pos=B.succession.factions.officials.join(',');
  assert.ok(!E.legalActions(g).some(a=>a.kind==='gain_support'));
});
test('phase boundary waits for grace round and keeps actual equipment and positions', () => {
  const g=game();const p=E.active(g);p.pos=B.checkpoint.join(',');p.equipment=B.equipment.slice();p.support=['army'];p.prestige=2;
  take(g,'claim_checkpoint');for(let i=0;i<3;i++)move(g);
  assert.equal(g.phase,1);assert.equal(g.round,2);
  for(let i=0;i<3;i++)move(g);
  const before=plain(g.players.map(p=>({id:p.id,equipment:p.equipment,support:p.support,prestige:p.prestige,pos:p.pos})));
  const actor=E.active(g), action=E.legalActions(g).find(a=>a.kind==='move');
  before.find(p=>p.id===actor.id).pos=action.dest;
  E.applyAction(g,action);assert.equal(g.phase,2);assert.equal(g.round,1);
  assert.deepEqual(plain(g.players.map(p=>({id:p.id,equipment:p.equipment,support:p.support,prestige:p.prestige,pos:p.pos}))),before);
  assert.equal(g.players.filter(p=>p.equipment.length===0).length,3);
});
test('city timeout never manufactures equipment', () => {
  const g=game();g.round=B.l1MaxRounds;g.turnIndex=3;g.players[1].equipment=[B.equipment[0]];
  move(g);assert.equal(g.phase,2);assert.equal(g.phase1Timeout,true);assert.equal(g.players[1].equipment.length,1);
  assert.equal(g.players[0].equipment.length,0);
});
test('claim needs two distinct supporters, succession, and the crossing', () => {
  const g=game(),p=E.active(g);p.pos=B.checkpoint.join(',');p.support=['army','elites'];
  assert.ok(!E.legalActions(g).some(a=>a.kind==='proclaim'));
  g.phase=2;p.support=['army'];assert.ok(!E.legalActions(g).some(a=>a.kind==='proclaim'));
  p.support.push('elites');assert.ok(E.legalActions(g).some(a=>a.kind==='proclaim'));
});
test('all three unique rivals receive a response before acclamation', () => {
  const g=claimingGame();take(g,'proclaim');assert.equal(g.pendingClaim.responded.length,0);
  move(g);assert.deepEqual(plain(g.pendingClaim.responded),['P1']);assert.equal(g.winner,null);
  // A repeated response must not use another rival's opportunity.
  g.turnIndex=1;move(g);assert.deepEqual(plain(g.pendingClaim.responded),['P1']);
  move(g);assert.deepEqual(plain(g.pendingClaim.responded),['P1','P2']);assert.equal(g.winner,null);
  move(g);assert.equal(g.winner,'P0');
});
test('response window survives the rotating round boundary and claimant turn', () => {
  const g=claimingGame();g.turnRoundStart=1;take(g,'proclaim');
  assert.equal(E.active(g).id,'P2');move(g);move(g);assert.equal(E.active(g).id,'P0');
  take(g,'maintain_claim');assert.equal(g.winner,null);
  move(g);assert.equal(g.winner,'P0');
});
test('successful paid challenge cancels and displaces claimant without taking progress', () => {
  const g=claimingGame();g.players[0].equipment=B.equipment.slice();take(g,'proclaim');
  const attacker=E.active(g),claimant=g.players[0];attacker.pos='5,6';attacker.prestige=1;
  g.diceOverrides={combat:[1,1]};
  const rec=take(g,'duel',{target:'P0',dest:'6,6',spend_prestige:true});
  assert.equal(g.pendingClaim,null);assert.equal(claimant.pos,claimant.gate);
  assert.equal(claimant.equipment.length,6);assert.equal(claimant.support.length,2);
  assert.ok(rec.events.some(e=>e.type==='prestige_spent'&&e.amount===1));
});
test('failed paid challenge spends before rolling and counts a response', () => {
  const g=claimingGame();take(g,'proclaim');const p=E.active(g);p.pos='5,6';p.prestige=1;
  g.diceOverrides={combat:[1,6]};take(g,'duel',{target:'P0',dest:'6,6',spend_prestige:true});
  assert.equal(p.prestige,0);assert.ok(g.pendingClaim);assert.deepEqual(plain(g.pendingClaim.responded),['P1']);
});
test('contest fee is mandatory and paid before any boost or die roll', () => {
  B.succession.contest_cost=1;
  const g=claimingGame();take(g,'proclaim');const p=E.active(g);p.pos='5,6';
  assert.ok(!E.legalActions(g).some(a=>a.kind==='duel'&&a.target==='P0'));
  p.prestige=1;
  assert.ok(E.legalActions(g).some(a=>a.kind==='duel'&&a.target==='P0'&&!a.spend_prestige));
  assert.ok(!E.legalActions(g).some(a=>a.kind==='duel'&&a.target==='P0'&&a.spend_prestige));
  p.prestige=2;g.diceOverrides={combat:[1,6]};
  const rec=take(g,'duel',{target:'P0',dest:'6,6',spend_prestige:true});
  assert.equal(p.prestige,0);
  assert.deepEqual(plain(rec.events.filter(e=>e.type==='prestige_spent').map(e=>e.purpose)),['claim_contest','challenge']);
  B.succession.contest_cost=0;
});
test('claimant leaving the crossing cancels the claim', () => {
  const g=claimingGame();take(g,'proclaim');g.turnIndex=0;move(g);assert.equal(g.pendingClaim,null);
});
test('guard duty requires movement and capped rewards are recorded', () => {
  const g=game(),p=E.active(g);p.pos=B.gloryPosts[0].join(',');
  assert.ok(!E.legalActions(g).some(a=>a.kind==='guard_post'&&a.dest===p.pos));
  p.pos='0,1';p.prestige=3;
  assert.ok(!E.legalActions(g).some(a=>a.kind==='guard_post'));
  B.gloryCap=null;assert.ok(E.legalActions(g).some(a=>a.kind==='guard_post'));B.gloryCap=3;
});
test('stale and forged actions fail before mutation', () => {
  const g=game(),action=E.legalActions(g)[0],before=JSON.stringify(g);
  assert.throws(()=>E.applyAction(g,{...action,target:'P9'}));assert.equal(JSON.stringify(g),before);
  E.applyAction(g,action);const after=JSON.stringify(g);assert.throws(()=>E.applyAction(g,action));assert.equal(JSON.stringify(g),after);
});
test('a completed response claim wins before the phase deadline', () => {
  const g=claimingGame();g.round=B.l2MaxRounds;take(g,'proclaim');move(g);move(g);move(g);
  assert.equal(g.winner,'P0');assert.equal(g.draw,false);
});
test('succession timeout produces an explicit draw', () => {
  const g=game();g.phase=2;g.round=B.l2MaxRounds;g.turnIndex=3;move(g);
  assert.equal(g.draw,true);assert.equal(g.phase2Timeout,true);assert.deepEqual(plain(E.legalActions(g)),[]);
});
test('bots ignore private mapping and random state', () => {
  const g=game(),acts=E.legalActions(g);
  const before=BOT.choose('balanced',g,acts,()=>0.5).action_id;
  const other={...g,equipmentMap:new Proxy({}, {get(){throw Error('private read');}}),rngStates:new Proxy({}, {get(){throw Error('private read');}})};
  assert.equal(BOT.choose('balanced',other,acts,()=>0.5).action_id,before);
});
function playForty(contestCost) {
  B.succession.contest_cost=contestCost;
  const summary={wins:0,draws:0,claims:0,cancellations:0,turns:0,contestFees:0,explores:0,duels:0};
  for(let i=0;i<40;i++){
    const kinds=i%4===0?['balanced','balanced','balanced','balanced']:i%4===1?['greedy','greedy','greedy','greedy']:i%4===2?['aggressive','aggressive','aggressive','aggressive']:['balanced','greedy','aggressive','random'];
    const g=E.newGame(1000+i*7,seats.map((s,j)=>({...s,kind:kinds[j]})));
    let turns=0;
    while(!g.winner&&!g.draw){
      assert.ok(++turns<=4*(B.l1MaxRounds+B.l2MaxRounds)+1);
      const acts=E.legalActions(g),p=E.active(g);
      const action=BOT.choose(p.kind,{...g,activePlayer:p},acts,g.rng);
      assert.ok(acts.includes(action));E.applyAction(g,action);
      for(const q of g.players){assert.ok(q.prestige>=0&&q.prestige<=B.gloryCap);assert.equal(new Set(q.equipment).size,q.equipment.length);assert.equal(new Set(q.support).size,q.support.length);}
    }
    summary[g.winner?'wins':'draws']++;summary.turns+=turns;
    const events=g.events.flatMap(r=>r.events);
    summary.claims+=events.filter(e=>e.type==='claim_proclaimed').length;
    summary.cancellations+=events.filter(e=>e.type==='claim_cancelled').length;
    summary.contestFees+=events.filter(e=>e.type==='prestige_spent'&&e.purpose==='claim_contest').reduce((n,e)=>n+e.amount,0);
    summary.explores+=g.events.filter(r=>r.kind==='explore').length;
    summary.duels+=g.events.filter(r=>r.kind==='duel').length;
    if(g.winner)assert.equal(g.pendingClaim.responded.length,3);
  }
  return summary;
}
const comparisons={};
for(const fee of [0,1])test(`40 varied bot games with contest fee ${fee} finish with legal moves and valid state`,()=>{comparisons[fee]=playForty(fee);});
B.succession.contest_cost=0;
console.log('Bot-game observations:', JSON.stringify(comparisons));
console.log('All succession engine tests pass.');
