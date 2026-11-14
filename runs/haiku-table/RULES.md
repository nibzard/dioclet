# Diocletian's Palace 0.9.4 - rules for this table

```
                                               QUICK REFERENCE
                                                             keep this beside the board

YOUR TURN
1. Roll two dice.
2. Move up to the total; stop early if you like.
3. Do ONE action (or none): take treasure · guard duty · duel · gain support · claim the checkpoint · proclaim · maintain
your claim.

TWO MAPS
Palace map (large): treasures, guard posts, opening claim.
Succession map (small): support, proclaiming, the whole endgame.
At the change everyone returns to their gate on the small map.

ROLLS
Movement: two dice summed.
Guard post: one die - 4+ earns 1 Prestige (palace map).
Duel: one die each + your one best item bonus; the pugio wins ties.

EQUIPMENT (one best bonus per side)
Gladius +1 attack · Scutum +1 defense · Pilum +1 vs the claimant.
Pugio wins ties · Galea once: reveal a district · Lorica once: stay when beaten.

PRESTIGE (cap 3)
Earn: guard post 4+ (palace) · any duel win - the only income on the succession map.
Spend: 1 = faction support · 1 = fee to contest a claim.
Lose: 1 to the bank whenever you lose a duel.

FACTIONS (succession map only)
Army (shield) east · officials (column) west · elites (laurel) north.
1 Prestige each, no roll. Two different factions needed to proclaim.

PROCLAIM
Succession phase, stand at the Peristyle, 2 supporters, no other claim standing.

CONTEST A CLAIM
Move within 2 circles of the claimant and duel them, any turn inside the window.
Mandatory fee: 1 Prestige before you roll.
Win: claim canceled, claimant returns to their gate on the succession map (lorica: stay put once), keeps everything.

WINNING
A claim that stands two full rounds =Diocletian's

No claim standing by succession round 24 = draw.
```

## Reading the seat view

- Coordinates are `[x, y]`; the map prints north at the top (`y` 12 down to 0).
- The game begins on the palace map (phase 1). When the phase changes, everyone
  returns to their gate on the smaller succession map (phase 2).
- Each candidate gives street distances after the move:
  - `peristyle`: the crossing (`X`) where you claim or proclaim.
  - `claim`: the current claim to contest.
  - `collection`: the nearest treasure you still need.
  - `prestige`: the nearest Prestige source.
- The engine rolls your dice for you before your turn. The view shows your roll.
- Only the shortlisted candidates are shown, but any listed id is legal.
