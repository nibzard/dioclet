// Check complete seeded action sequences against the Python succession engine.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';
const root = new URL('../', import.meta.url);
const rules = JSON.parse(readFileSync(new URL('rules_v08_succession.json', root), 'utf8'));
const python = String.raw`
import copy,json,sys,random
import engine,succession
payload=json.load(sys.stdin)
def norm_action(a):
 return {'kind':a['kind'],'dest':','.join(map(str,a['destination'])),'target':a.get('target'),'faction':a.get('faction'),'spend_prestige':a.get('spend_prestige'),'contest_cost':a.get('contest_cost')}
def snapshot(g):
 pending=g['pending_claim']
 return {'phase':g['phase'],'round':g['round'],'turn':g['turn_id'],'active':g['active_player'],
 'order':g['turn_order'],'round_start':g['round_start'],'roll':g['current_roll'],
 'dice':g['current_dice'] if g['current_roll'] is not None else [],
 'first':g['first_challenger'],'winner':g['winner'],'draw':g['phase2_timeout'],
 'phase1_timeout':g['phase1_timeout'],'rounds1':g['rounds_level1'],
 'pending':None if pending is None else {'player':pending['player'],'id':pending['claim_id'],'responded':sorted(pending['responded'])},
 'players':{pid:{'gate':','.join(map(str,p['gate'])),'gate_id':p['gate_id'],'pos':','.join(map(str,p['pos'])),'prestige':p['prestige'],'support':sorted(p['support']),'equipment':sorted(p['equipment']),'turns':p['turns']} for pid,p in g['players'].items()},
 'revealed':{','.join(map(str,g['rules']['board']['districts'][n])):v for n,v in g['revealed'].items()},
 'mapping':{','.join(map(str,g['rules']['board']['districts'][n])):v for n,v in g['district_equipment'].items()},'rng':dict(g['rng'])}
cases=[]
for scenario in ['city','prepared']:
 for fee in [0,1]:
  for seed in [1,2026,71519]:
   r=copy.deepcopy(payload['rules']);r['succession']['contest_cost']=fee
   if seed==71519:r['succession']['gate_assignment']='rotation';r['succession']['gate_rotation']=2;r['glory']['cap']=None
   if seed==1:r['succession']['support_in_city']=False;r['turns']['rotate_first_player_each_round']=False
   g=engine.new_game(r,seed,'parity');prng=random.Random(seed+fee)
   if scenario=='prepared':
    g['phase']=2
    for i,(pid,p) in enumerate(g['players'].items()):
     p['pos']=r['board']['checkpoint'][:];p['prestige']=2;p['support']=['army','elites'];p['equipment']=r['equipment'][:3+i%2*3]
   case={'rules':r,'seed':seed,'scenario':scenario,'initial':snapshot(g),'steps':[]}
   while not engine.is_finished(g):
    available=engine.legal_actions(g)
    priority=[a for a in available if a['kind']=='proclaim'] or [a for a in available if a['kind']=='maintain_claim']
    if not priority and g['pending_claim']:
     priority=[a for a in available if a['kind']=='duel' and a.get('target')==g['pending_claim']['player']]
    if not priority:priority=[a for a in available if a['kind']=='gain_support'] or [a for a in available if a['kind']=='claim_checkpoint'] or [a for a in available if a['kind']=='explore']
    if not priority and g['players'][g['active_player']]['prestige']<2:
     priority=[a for a in available if a['kind']=='guard_post'] or [a for a in available if a['kind']=='duel' and not a.get('spend_prestige')]
    chosen=prng.choice(priority or available)
    action=norm_action(chosen)
    legal=[norm_action(a) for a in available]
    rec=engine.apply_action(g,g['active_player'],g['turn_id'],chosen['action_id'],'parity')
    case['steps'].append({'action':action,'legal':legal,'dice':rec['dice_used'],'after':snapshot(g)})
    assert len(case['steps'])<=192
   cases.append(case)
json.dump(cases,sys.stdout)
`;
const proc = spawnSync('python3', ['-c', python], { cwd: root, input: JSON.stringify({rules}), encoding:'utf8', maxBuffer:32*1024*1024 });
if(proc.status!==0)throw Error(proc.stderr||proc.stdout);
const cases = JSON.parse(proc.stdout);
const plain = value => JSON.parse(JSON.stringify(value));
function load(r) {
 const b=r.board;
 const B={...b,mode:r.gameplay_mode,succession:r.succession,equipment:r.equipment,
  gloryPosts:b.glory_posts,level2:b.level2_sites,movement:{sides:r.movement.die_sides,count:r.movement.dice_count,duelRange:r.movement.duel_range,allowStationary:r.movement.allow_stationary_special_actions},
  gloryCap:r.glory.cap,prestigeRules:r.glory,combatRules:r.combat,rotateFirst:r.turns.rotate_first_player_each_round,
  l1MaxRounds:r.level1.max_rounds,l2MaxRounds:r.level2.max_rounds,graceRounds:r.level1.grace_full_rounds};
 const c=vm.createContext({console,structuredClone,DIOCLET_BOARD:B});
 for(const file of ['engine.js','succession-engine.js'])vm.runInContext(readFileSync(new URL('web/'+file,root),'utf8'),c);
 return {E:c.DIOCLET_ENGINE,B};
}
function normAction(a){return {kind:a.kind,dest:a.dest,target:a.target??null,faction:a.faction??null,spend_prestige:a.spend_prestige??null,contest_cost:a.contest_cost??null};}
function snapshot(g,E){return plain({phase:g.phase,round:g.round,turn:g.turnSeq,active:E.active(g).id,order:g.order,round_start:g.turnRoundStart,roll:g.currentRoll?.total??null,dice:g.currentRoll?.dice??[],first:g.firstClaimer,winner:g.winner,draw:g.phase2Timeout,phase1_timeout:g.phase1Timeout,rounds1:g.roundsLevel1,
 pending:g.pendingClaim&&{player:g.pendingClaim.claimant,id:g.pendingClaim.id,responded:g.pendingClaim.responded.slice().sort()},
 players:Object.fromEntries(g.players.map(p=>[p.id,{gate:p.gate,gate_id:p.gateId,pos:p.pos,prestige:p.prestige,support:p.support.slice().sort(),equipment:p.equipment.slice().sort(),turns:p.turns}])),revealed:g.revealed,mapping:g.equipmentMap,rng:Object.fromEntries(Object.keys(g.rngStates).filter(k=>k!=='bots').map(k=>[k,g.rngStates[k]]))});}
let turns=0;
for(const c of cases){
 const {E,B}=load(c.rules),seats=['P0','P1','P2','P3'].map(id=>({id,name:id,kind:'human'})),g=E.newGame(c.seed,seats);
 if(c.scenario==='prepared'){
  g.phase=2;g.players.forEach((p,i)=>{p.pos=B.checkpoint.join(',');p.prestige=2;p.support=['army','elites'];p.equipment=B.equipment.slice(0,3+i%2*3);});
 }
 const label=`${c.scenario} seed=${c.seed} fee=${B.succession.contest_cost}`;
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
