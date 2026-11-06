> **Engine caveat:** this game ran before the emperor-miss retreat
> bug was fixed (the miss-retreat to `[2,3]` was overwritten; see
> FINDINGS.md §6). Impressions that the retreat penalty "never
> fired" trace to that bug, not to the rules. Other observations
> stand.

# Narrative game 3: four personas, seed 4103

Playtest date: 2026-11-06. Rules: `rules_baseline.json`, run `runs/narr3`,
seat order P1, P0, P2, P3.

## Outcome

- Winner: P2 Sabina, on her second Emperor hit (`emperor_hit`, turn 59).
- `runs/narr3/result.json`: 15 rounds (9 Level 1, 6 Level 2), 59 turns,
  no timeout. Sabina was also First Challenger and won. P2 finished with
  2 hits, the others with 1 each, all four inside the Emperor chamber.
- `sim.py replay --run runs/narr3 --verify` reports `verified: true`.

## How the four personas experienced the same rules

- Sabina (tactician) had the most satisfying game. She never initiated a
  duel, spent exactly 2 Glory (1 for peristyle tempo, 1 on an Emperor
  swing), and won. Her seat helped: the south gate `[2,4]` is the Emperor
  chamber, so she started Level 2 on the boss tile.
- Nerva (paranoid) suffered the most. She reached the cap of 2 Glory in
  round 3 and spent 0 all game. Her Emperor swing on turn 50 lost 7-8;
  one coin would have made it 9-8 and won the game. She ended with 1 hit
  from 4 attempts and a full purse nobody would let her bank.
- Gaius (glory-hound) was bored in Level 1. The cap of 2 filled on turn 4
  and no sink exists in Level 1, so 6 of his duel rewards were logged
  `glory_wasted_at_cap`. He sat at cap for six rounds doing nothing that
  paid. Level 2 gave him a shop and he spent both coins without hesitating.
- Rufus (reckless kid) had the most fun and stayed competitive. He
  initiated 6 of the game's 11 duels, lost 5, then hit the Emperor for
  free and finished 1 hit from the win. Auto-equip flattened his 2-item
  kit into 6, so his Level 1 mischief cost him nothing.
- The tie-to-defender rule decided 3 of 11 duels (6-6, 1-1, 5-5), all as
  defender Gaius beating attacker Rufus. Rufus lost the rivalry on ties
  alone, which felt unfair to play rather than strategic.
- Cap of 2 Glory: it hurt everyone who reached it. Seven duel rewards were
  wasted across the game, and guard posts became illegal once capped. It
  helped only Sabina, who read a coin as "one planned purchase" and spent
  both at moments she chose.
- Level 1 felt like a forced march once the checkpoint fired. Sabina
  triggered it in round 7; the two grace rounds gave Nerva one useful
  explore and everyone else dead turns.

## Engine defect found during play

- A failed Emperor attack does not retreat. `engine.py` line 661 sets
  `me["pos"]` to the retreat node `[2,3]`, then lines 674-675 overwrite
  the position with the action destination `[2,4]`. SPEC section 7 says
  a failed attempt moves the player to the retreat node.
- Effect on this game: a miss cost no tempo. All four players camped in
  the chamber and re-attacked each round. Nerva missed three times and
  never left the room. Fix the overwrite before judging Emperor difficulty.

## Next single-knob experiments

1. `glory.cap: 3`, to stop wasted rewards for duel-heavy players.
2. `glory.duel_win_reward: 1` but only below cap, plus a Level 1 sink, so
   Gaius has something to buy before round 9.
3. `combat.tie_goes_to_defender: false`, to stop the coin-flip duels that
   decided Rufus's whole level.
