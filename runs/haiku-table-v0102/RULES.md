# Diocletian's Palace 0.10.2 big board - rules for this table

```
                                      QUICK REFERENCE
                                                      keep this beside the board

YOUR TURN
1. Roll two dice.
2. Move up to the total; stop early if you like.
3. Do ONE action (or none): take treasure · guard duty · duel · search a card · gain support · claim the checkpoint ·
proclaim · maintain your claim.

TWO MAPS
Palace map (large): treasures, the checkpoint claim.
Claim the checkpoint: own ALL SIX items and stand at the Peristyle. The palace map ends one full round after the first
claim, or after palace round 24 if nobody owns all six.
Succession map (the back of the board): support, proclaiming, the whole endgame.
At the change everyone returns to their gate on the succession map; every gate is 9 steps from the Peristyle.

ROLLS
Movement: two dice summed.
Guard post: one die - 4+ earns 1 Prestige (either map).
Duel: one die each + your one best item bonus; the pugio wins ties.

EQUIPMENT (one best bonus per side)
Gladius +1 attack · Scutum +1 defense · Pilum +1 vs the claimant.
Pugio wins ties · Galea once: reveal a district · Lorica once: stay when beaten.

PRESTIGE (cap 3)
Earn: guard post 4+ (either map) · any duel win.
Spend: 1 = faction support · 1 = fee to contest a claim. Searching is free.
Keep 1 in reserve: with 0 Prestige you cannot contest a claim.
Lose: 1 to the bank whenever you lose a duel.

FACTION CARDS (succession map only)
Six cards face down on the ? spaces: army, officials, elites, and three empty streets.
Search: end your move on a ? and turn the card face up (your action).
Support: on a face-up faction, 1 Prestige, no roll. Two different factions needed to proclaim.

PROCLAIM
Succession phase, stand at the Peristyle, 2 supporters, no other claim standing.

CONTEST A CLAIM
Move within 2 circles of the claimant and duel them, any turn inside the window.
Mandatory fee: 1 Prestige before you roll.
Win: claim canceled, claimant returns to their gate on the succession map (lorica: stay put once), keeps everything.

WINNING
A claim that stands two full rounds = emperor.
No claim standing by succession round 24 = draw.

```

## Reading the seat view

- Coordinates are `[x, y]`; the map prints north at the top (`y` 0 down to 12), as on the printed board.
- The game begins on the palace map (phase 1). When the phase changes, everyone
  returns to their gate on the succession map (phase 2). It is the same size,
  with the same six blocks and streets.
- On the map, `*` is a guard post. Both maps have guard posts.
- The palace checkpoint claim (phase 1) only starts the succession. It is not a
  claim to the throne. In phase 2, "standing claim" shows the claim you can
  contest and the round it wins.
- Each candidate gives street distances after the move:
  - `peristyle`: the Peristyle (`X`), where you claim or proclaim.
  - `claim`: the current claim to contest.
  - `collection`: the nearest treasure you still need.
  - `prestige`: the nearest Prestige source.
- The engine rolls your dice for you before your turn. The view shows your roll.
- Only the shortlisted candidates are shown, but any listed id is legal.
