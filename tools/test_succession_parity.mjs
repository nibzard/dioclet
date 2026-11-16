// Check complete seeded action sequences against the Python succession
// engine on the V0.10.2 twin-board rules. Three scenario families:
// 'city' (natural games), 'prepared' (hand-built phase 2 with no dealt
// faction sites, exercising the fixed-cells fallback), and 'blind'
// (a forced checkpoint claim so the phase transition, gate reset, and
// blind faction deal run inside the replay).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';
const root = new URL('../', import.meta.url);
const rules = JSON.parse(readFileSync(new URL('rules/imperial-rivals-v0.10.2.json', root), 'utf8'));
const python = String.raw`
import copy,json,sys,random
import engine
payload=json.load(sys.stdin)
def norm_action(a):
 return {'kind':a['kind'],'dest':','.join(map(str,a['destination'])),'target':a.get('target'),'faction':a.get('faction'),'district':a.get('district'),'spend_prestige':a.get('spend_prestige'),'contest_cost':a.get('contest_cost')}
def snapshot(g):
 pending=g['pending_claim']
 return {'phase':g['phase'],'round':g['round'],'turn':g['turn_id'],'active':g['active_player'],
 'order':g['turn_order'],'round_start':g['round_start'],'roll':g['current_roll'],
 'dice':g['current_dice'] if g['current_roll'] is not None else [],
 'first':g['first_challenger'],'trigger':g['trigger_round'],
 'winner':g['winner'],
 # The web engine still uses the pre-rename end word; compare through it.
 'end':{'succession_timeout':'phase2_timeout'}.get(g['end_reason'],g['end_reason']),
 'draw':g['succession_timeout'],'status':g['status'],
 'phase1_timeout':g['palace_timeout'],'rounds1':g['rounds_palace'],
 'equip_at_transition':g['equipment_at_transition'],
 'pending':None if pending is None else {'player':pending['player'],'id':pending['claim_id'],'round':pending['round'],'responded':sorted(pending['responded'])},
 'players':{pid:{'gate':','.join(map(str,p['gate'])),'gate_id':p['gate_id'],'pos':','.join(map(str,p['pos'])),'prestige':p['prestige'],'support':sorted(p['support']),'equipment':sorted(p['equipment']),'turns':p['turns'],'abilities':dict(sorted(p['abilities_used'].items()))} for pid,p in g['players'].items()},
 'revealed':dict(g['revealed']),'mapping':dict(g['district_equipment']),
 'faction_sites':None if g['faction_sites'] is None else dict(sorted(g['faction_sites'].items())),
 'faction_revealed':None if g['faction_sites_revealed'] is None else dict(sorted(g['faction_sites_revealed'].items())),
 'rng':dict(g['rng'])}
cases=[]
for scenario in ['city','prepared','blind']:
 for fee in [0,1]:
  for seed in [1,2026,71519]:
   r=copy.deepcopy(payload['rules']);r['succession']['contest_fee']=fee
   if seed==71519:r['prestige']['cap']=None
   if seed==1:r['turns']['rotate_first_player_each_round']=False
   g=engine.new_game(r,seed,'parity');prng=random.Random(seed+fee)
   if scenario=='prepared':
    g['phase']=2
    for i,(pid,p) in enumerate(g['players'].items()):
     p['pos']=r['succession']['map']['checkpoint'][:];p['prestige']=2;p['support']=['army','elites'];p['equipment']=r['treasures']['items'][:3+i%2*3]
   if scenario=='blind':
    g['first_challenger']='P0';g['trigger_round']=g['round']
   case={'rules':r,'seed':seed,'scenario':scenario,'initial':snapshot(g),'steps':[]}
   while not engine.is_finished(g):
    available=engine.legal_actions(g)
    priority=[a for a in available if a['kind']=='proclaim'] or [a for a in available if a['kind']=='maintain_claim']
    if not priority and g['pending_claim']:
     priority=[a for a in available if a['kind']=='duel' and a.get('target')==g['pending_claim']['player']]
    if not priority:priority=[a for a in available if a['kind']=='search_site'] or [a for a in available if a['kind']=='gain_support'] or [a for a in available if a['kind']=='claim_checkpoint'] or [a for a in available if a['kind']=='explore']
    if not priority and g['players'][g['active_player']]['prestige']<2:
     priority=[a for a in available if a['kind']=='guard_post'] or [a for a in available if a['kind']=='duel' and not a.get('spend_prestige')]
    chosen=prng.choice(priority or available)
    action=norm_action(chosen)
    legal=[norm_action(a) for a in available]
    rec=engine.apply_action(g,g['active_player'],g['turn_id'],chosen['action_id'],'parity')
    case['steps'].append({'action':action,'legal':legal,'dice':rec['dice_used'],'after':snapshot(g)})
    assert len(case['steps'])<=600
   cases.append(case)
json.dump(cases,sys.stdout)
`;
const proc = spawnSync('python3', ['-c', python], { cwd: root, input: JSON.stringify({rules}), encoding:'utf8', maxBuffer:64*1024*1024 });
if(proc.status!==0)throw Error(proc.stderr||proc.stdout);
const cases = JSON.parse(proc.stdout);
const plain = value => JSON.parse(JSON.stringify(value));
function load(caseRules) {
  const ctx = vm.createContext({console,structuredClone});
  vm.runInContext(readFileSync(new URL('web/board-data.js',root),'utf8'),ctx);
  const B = ctx.DIOCLET_BOARD;
  // The Python side mutates its rules per case; the engines read these
  // board fields live, so the same mutations apply here.
  B.succession.contestCost = caseRules.succession.contest_fee;
  if (caseRules.prestige.cap === null) B.glory.cap = null;
  if (caseRules.turns.rotate_first_player_each_round === false) B.rotateFirst = false;
  vm.runInContext(readFileSync(new URL('web/engine.js',root),'utf8'),ctx);
  vm.runInContext(readFileSync(new URL('web/succession-engine.js',root),'utf8'),ctx);
  return {E:ctx.DIOCLET_ENGINE,B};
}
function normAction(a){return {kind:a.kind,dest:a.dest,target:a.target??null,faction:a.faction??null,district:a.district??null,spend_prestige:a.spend_prestige??null,contest_cost:a.contest_cost??null};}
function snapshot(g,E){return plain({phase:g.phase,round:g.round,turn:g.turnSeq,active:E.active(g).id,order:g.order,round_start:g.turnRoundStart,roll:g.currentRoll?.total??null,dice:g.currentRoll?.dice??[],first:g.firstClaimer,trigger:g.triggerRound,
 winner:g.winner,end:g.endReason,draw:g.phase2Timeout,status:g.status,
 phase1_timeout:g.phase1Timeout,rounds1:g.roundsLevel1,equip_at_transition:g.equipmentAtTransition,
 pending:g.pendingClaim&&{player:g.pendingClaim.player,id:g.pendingClaim.claimId,round:g.pendingClaim.round,responded:g.pendingClaim.responded.slice().sort()},
 players:Object.fromEntries(g.players.map(p=>[p.id,{gate:p.gate,gate_id:p.gateId,pos:p.pos,prestige:p.prestige,support:p.support.slice().sort(),equipment:p.equipment.slice().sort(),turns:p.turns,abilities:Object.fromEntries(Object.keys(p.abilitiesUsed).sort().map(k=>[k,p.abilitiesUsed[k]]))}])),
 revealed:g.revealed,mapping:g.districtEquipment,
 faction_sites:g.factionSites&&Object.fromEntries(Object.keys(g.factionSites).sort().map(k=>[k,g.factionSites[k]])),
 faction_revealed:g.factionSitesRevealed&&Object.fromEntries(Object.keys(g.factionSitesRevealed).sort().map(k=>[k,g.factionSitesRevealed[k]])),
 rng:Object.fromEntries(Object.keys(g.rngStates).filter(k=>k!=='bots').map(k=>[k,g.rngStates[k]]))});}
let turns=0;
for(const c of cases){
 const {E,B}=load(c.rules);
 const seats=['P0','P1','P2','P3'].map(id=>({id,name:id,kind:'human'}));
 const g=E.newGame(c.seed,seats);
 if(c.scenario==='prepared'){
  g.phase=2;g.players.forEach((p,i)=>{p.pos=B.boardLevel2.checkpoint.join(',');p.prestige=2;p.support=['army','elites'];p.equipment=B.equipment.slice(0,3+i%2*3);});
 }
 if(c.scenario==='blind'){
  g.firstClaimer='P0';g.triggerRound=g.round;g.transitionAt=Math.min(g.round+B.graceRounds,B.l1MaxRounds);
 }
 const label=`${c.scenario} seed=${c.seed} fee=${c.rules.succession.contest_fee}`;
 assert.deepEqual(snapshot(g,E),c.initial,label+' initial state');
 for(const [i,step] of c.steps.entries()){
  const legal=E.legalActions(g);
  assert.deepEqual(plain(legal.map(normAction)),step.legal,label+' legal actions at '+i);
  const a=legal.find(a=>JSON.stringify(normAction(a))===JSON.stringify(step.action));
  assert.ok(a,label+' selected action at '+i);
  const rec=E.applyAction(g,a);
  assert.deepEqual(plain(rec.dice),step.dice,label+' combat dice at '+i);
  assert.deepEqual(snapshot(g,E),step.after,label+' state after '+i+' '+a.kind);
  turns++;
 }
 console.log('  ok:',label,`(${c.steps.length} turns)`);
}
console.log(`${cases.length} full action sequences and ${turns} turns match between Python and JavaScript.`);
