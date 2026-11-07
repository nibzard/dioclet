# tb209: the dominant Decisions win

**Outcome:** P0 (decisions) won by Emperor at turn 53 (round 6 of phase 2; 14 rounds total).
Seats: P0 decisions, P1 tactical, P2 decisions, P3 tactical; order P0, P2, P1, P3. `comeback_win: true`.

## Reconstruction of the decisive stretches

**Opening (t2).** P0's first choice, 16 candidates shown of 45 legal. It chose `a0022`
"Move to district B (unrevealed) and explore it." (confidence 0.19; top: a0022 0.24,
move-to-[2,1] 0.16, explore-E 0.09). Duel candidates ("exact win chance 58%") drew 0.02 to
0.04. Result: district B revealed (gladius); follow-ups E (t15) and D (t21). Three
explores, three gains, `explore_no_gain: 0`.

**Glory engine (t12, t28, t31).** At t12 the model picked `a0003` "Duel P3 (exact win
chance 58%; target has 0 Emperor hits, 1 Glory)" at p=0.15, confidence 0.06, over explore-F
(0.13) and moves toward [2,4] (0.13). Result: won 3-2, +1 Glory. At t28 it took `a0003`
"Duel P2 ... 58%" (p=0.22, confidence 0.17). Result: 6+1=7 vs 6+1=7; the engine awards ties
to the attacker, so +1 Glory. At t31, "Duel P2 ... 58%" again at p=0.44, confidence 0.30.
Result: 4+1=5 vs 4+1=5, another tie won; Glory sat at the cap of 2, so this award was
wasted (`glory_wasted_at_cap: 1`).

**Checkpoint and transition (t26-t32).** P1 (tactical) was first challenger at t26. The
phase transition fired on t32 and auto-granted equipment to the cap: P0 +3 to reach 6/6,
P2 +2 to 6/6. P1 and P3 had already collected 6 by hand. Measured fact: P0's 3 items and
P1's 6 produced the same +2 duel bonus in phase 2.

**Seal acquisition (t34, t44, t47).** On its first phase-2 turn, reset to gate [2,0] with
die 6, P0 chose `a0003` "Attempt a seal at [2, 2] by spending 1 Glory (guaranteed); exact
success chance 100%." (p=0.27, confidence 0.22) over the 33% peristyle roll (0.04), the 67%
cellars roll after moving (a0037, 0.17), and the 58% barracks roll (0.11). Result: first
seal of the game, order 1, Glory 2 to 1. P1 attacked P0 at t36 and lost 6-3; P0 dueled back
at t37 (`a0001`, p=0.22), won 5-3, and landed at [1,2] beside the cellars. At t44 it moved
to [1,1] (p=0.46, confidence 0.42) rather than roll at once (67%, p=0.33). At t47 it took
`a0001` "Attempt a seal at [1, 1] by rolling; exact success chance 67%" (p=0.63,
confidence 0.61). Result: roll 6, second seal; 2 Glory still banked.

**Emperor attacks (t50, t53).** At t50: `a0002` "Attack the Emperor, spending 1 Glory for
+2; exact hit chance 72%." at p=0.73, confidence 0.71; the free 42% attack got 0.21.
Result: 2+2+2=6 vs Emperor 2+2=4, hit 1. At t53: the same action, now flagged "wins the
game on a hit", at p=0.91 and confidence 0.90, the game high. Result: 3+2+2=7 vs 1+2=3,
hit 2, `game_won`.

## Why this was strong play

- Perfect Emperor conversion, measured: 2 attempts, 2 hits. Both attacks were made at the
  slate's stated 72%, so the recorded win probability by t53 was about 0.72 x 0.72 = 52%.
- Endgame speed, measured: seal on phase-2 turn 1 (t34), second seal on turn 4 (t47), first
  attack on turn 5 (t50), win on turn 6 (t53). Every P0 phase-2 turn yielded a seal, a duel
  win, or a hit; `turns_skipped: 0`.
- Glory timing, measured: 5 duel awards funded 3 spends, and each spend bought a decisive
  edge: a 100% first seal, and +2 that lifted attacks from 42% to 72%.
- Route efficiency, measured: 3 explores for 3 items, 0 wasted moves. The transition
  auto-grant topped P0 to 6/6 anyway, so the sparse exploring cost nothing in duel bonus.
- The t50 and t53 distributions put nearly all mass on the paid attack (0.73, then 0.91)
  over the free 42% attack (0.21, then 0.08). The recorded probabilities are the evidence.
- 5-0 in duels (4 as attacker, 1 as defender). Two wins came on 7-7 and 5-5 ties, which the
  engine gives to the attacker, so the 58% slate chance understates attacker position. The
  rolls are fact; the tie-rule reading is interpretation.
- Interpretation: P0 treated phase 1 as a Glory engine (4 duels) while tactical seats
  explored. The slate descriptions advertise the duel payoff ("target has 0 Emperor hits,
  1 Glory"), and the auto-grant made extra items worthless. Logs show behavior, not motive.
- Caveats, measured: the t31 and t37 duels were fought at the Glory cap, wasting 2 awards,
  and the t44 move deferred a legal 67% roll by one turn. Neither slip cost a turn.

## Tactical seats

P1 and P3 hand-collected all 6 equipment that the auto-grant gave P0 for free, then ground
seal rolls (P3 rolled three consecutive 1s at the peristyle, t43, t46, t49); neither seat
ever attempted the Emperor, and P1's second seal landed at t52, after P0's first hit.

## Correction (PR review reconciliation, 2026-11-07)

The line above saying the winner worked "2 guard posts" is wrong. The
engine record (`result.json`, `events.jsonl`) for winner P0 shows
`guard_post_attempts: 0`; every Glory point came from duels (4/4 wins
attacking plus 1 defensive win; 3 Glory kept, 2 duel wins wasted at
the cap of 2; 3 spent: the Peristyle seal and two boosted Emperor
attacks). The Glory-engine reading stands — it was fueled entirely by
favorable fights, with the auto-grant completing the kit from 3
collected items. This strengthens the tournament-wide guard-post
finding: not even this dominant winner used one.
