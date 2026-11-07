# tb202: the Decisions seats lose badly

**Outcome:** P2 (tactical) won by Emperor at turn 57 (round 6 of phase 2; 15 rounds
total), `end_reason: emperor`, `comeback_win: true`. Seats: P0 tactical, P1 decisions,
P2 tactical, P3 decisions; turn order P2, P1, P3, P0; seed 5302. Emperor attempts:
P2 4 (2 hits), P1 1 (0 hits), P3 0. P0 and P3 died with `glory_final` 2 and 1, unspent.

## Reconstruction

**Phase 1 tempo and Glory.** P1 explored at t3, t6, t16, t19, t22, t32 (6th district
round 8); P3 at t7, t10, t13, t20, t26, t29 (round 8). Both burned turns on pure moves
(P1 t9, t25, t35; P3 t4, t23; the t23 move wasted a die of 6), and P1 sat 1 step from
[2,2] at t32 while P0 claimed the t30 checkpoint (+1 Glory). Both declined every guard
post offered: t19 P1 gave it p=0.06 vs explore 0.34; t32 P1 0.08 vs 0.36; t29 P3 0.05
vs 0.30. So `glory_earned` stayed 0 for P1 and P3 in phase 1, while P2 banked 1 at t34.

**Interference backfires (t36, t52).** P3's t36 pick `a0017` "Duel P2 (72%)" p=0.44,
confidence 0.40, lost 5-7 and paid P2 +1 Glory. P1's t52 pick `a0007` "Duel P2 (58%;
target has 1 Emperor hits)" p=0.31, confidence 0.26, over the peristyle seal (0.06)
and moves (max 0.14), lost 3-5 and paid P2 its third Glory. The decisions seats funded
2 of P2's 3 Glory with failed duels.

**Seals.** With no Glory, the guaranteed peristyle buy (1 Glory, 100%) never appeared
on a decisions slate; both had to roll. P1: cellars [1,1] t39 (67% site, roll 3, hit);
barracks [3,1] t42 fail (6 vs 7), t45 hit (7 vs 6) — second seal round 3. P3: cellars
t40 (roll 5, hit); barracks t43 fail (3 vs 6), t46 fail (5 vs 7), t49 hit (7 vs 4) —
second seal round 4, three tries at a 58% site.

**Emperor-relevant turns.** For P1, `attack_emperor` appeared once, at t55, and was
chosen: `a0001` "Attack the Emperor without Glory; exact hit chance 42%" p=0.32,
confidence 0.27, over move to [2,4] (0.25) and duel P2 (0.02). Roll 2 gave 4 vs 7,
miss, retreat to [2,3]. At t52 P1 held 2 seals but the attack was illegal: 3 tiles
from the goal with movement die 2, so the slate held only duels, moves, and the 33%
peristyle roll. For P3, `attack_emperor` never appeared in any of its 14 candidate
sets. Its only 2-seal turn was t56: die 1 from [3,1], goal 3 tiles away, slate was
3 duels plus 4 one-step moves. It picked `a0003` "Duel P2 (58%; target has 1 Emperor
hits)" p=0.55, confidence 0.48, won 8-7, and banked the Glory it died with.

**Winner's sequence.** P2 spent its t34 Glory on the peristyle seal at t38
(`seal_buy_at_cap`, no roll), rolled cellars at t41 (roll 5), then attacked every round
from round 3: t48 hit with a Glory boost (5 vs 3), t51 miss (4 vs 6), t54 miss with a
boost (6 vs 7), t57 hit unboosted (8 vs 5) for the win. The t38 and t54 spends ran on
Glory the decisions seats handed over at t36 and t52.

## Diagnosis

- Not a nerve failure: when the slate offered the attack, P1 took it (t55, top choice
  at p=0.32). The log shows a window failure, not a declined one.
- Zero Glory generation is the root cause. `guard_post_attempts: 0` for both seats all
  game; the slates offered 50% posts at least 18 times. One success buys the
  guaranteed peristyle seal and skips the barracks queue that cost P3 rounds 2-4.
- Seal tempo set attack volume: second seals t41 (P2), t45 (P1), t49 (P3), t53 (P0)
  gave P2 four swings, P1 one, P3 zero. At a stated 42% per swing, volume decided it.
- Movement dice closed the doors seals left open: P1 t52 (die 2, 3 tiles out) and P3
  t56 (die 1, 3 tiles out) had no legal attack candidate, so neither seat ever
  declined a live Emperor attack after sealing.
- Dice bit at the margins: P1's t42 miss was 6 vs 7, P3's t46 was 5 vs 7, and P1's t55
  was unwinnable even with a +2 boost (6 vs 7). But P2 also missed twice; its hits
  (5-3, 8-5) came from four swings, not hot dice.
- Interference was attempted and counterproductive: the t36 and t52 duels on P2 both
  lost and funded P2's t38 seal buy and t54 boost. P3's t56 duel won, but duels remove
  no hits or seals (`glory_stolen: 0`) and landed one turn before the win.
- The unspent Glory was stranded, not hoarded: P3 earned its only Glory on t56, its
  final turn; P0 held 1 seal until t53 and never had 2 seals plus reach. No declined
  spend exists in the log.
- Route drag was secondary: 5 pure-move turns of 18 cost the t30 checkpoint Glory.

**Verdict:** Weak play, amplified by dice. The decisions policy never built the Glory
that buys guaranteed seals and boosted attacks, so it got 1 Emperor swing to P2's 4.
