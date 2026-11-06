> **Engine caveat:** this game ran before the emperor-miss retreat
> bug was fixed (the miss-retreat to `[2,3]` was overwritten; see
> FINDINGS.md §6). Impressions that the retreat penalty "never
> fired" trace to that bug, not to the rules. Other observations
> stand.

# Narrative game 5 — Level 2 endgame feel

- Run: `runs/narr5`, seed 4105, rules `rules_baseline.json`.
- Result (`runs/narr5/result.json`): win by P2 "Vela", reason `emperor`,
  2 hits. 15 rounds, 56 turns (36 Level 1, 20 Level 2).
  `comeback_win: true`. First Challenger P0 did not win.
- Personas held: Stratega bought the peristyle seal with Glory in Level 2
  round 1. Hasta spent no Glory on seals and saved his one coin for the
  Emperor. Vela gambled at the barracks and at both Emperor attacks.
  Stola always took the nearest site.

## Endgame feel

- The seal race was fast and clean. All four players held one seal after
  Level 2 round 1 and two seals by round 3 or 4. Nobody ever felt locked
  out of the Emperor fight.
- Seal failures barely stung. Hasta failed the cellars twice (rolls 2 and
  1) before passing on roll 3. He lost two turns and no position, because
  retries are stationary. Frustration stayed low.
- The peristyle Glory buy was the most satisfying move of the game. One
  token turned the worst odds site (5-6) into a certainty. Two players
  used it. It reads as underpriced: 1 Glory for a guaranteed seal.
- The barracks gamble suited Vela. Both barracks attempts won on the
  first try (7-3 and 6-3). With full equipment the player is a clear
  favorite, so it feels like a skill check, not a coin flip.
- The Emperor miss-retreat never fired. Engine bug: `engine.py` line 661
  sets the pawn to the retreat node on a miss, then lines 674-675
  overwrite the position with the action destination. Players stayed in
  the chamber and re-attacked next turn. This breaks SPEC line 171 and
  the invariant at SPEC line 371. The intended walk-back sting is absent.
- The tie rule was the real sting. Three Glory-fueled attacks missed on
  ties (P0 7-7, P3 7-7, P1 6-6). A spent coin lost to a tie felt harsh
  but fair. Two of those ties landed in the same round, which piled the
  pain onto one turn of the game.
- The race to two hits was tense. After Vela's first hit, P0 answered in
  the next round. All four seats attacked the Emperor in rounds 4 and 5.
  The lead stayed in doubt until Vela closed 9-5.
- Boring stretch: the Level 1 grace rounds. Three of four players sat at
  the Glory cap with nothing to gain. Guard posts, duels, and exploring
  all paid zero, so they just moved. Capped players need a legal action
  during grace, or the cap needs to rise.
- Vela explored only 2 of 6 districts and won anyway. The auto-equip
  catch-up rule erased her whole Level 1 deficit, and her guard post luck
  (2 for 2) funded both Emperor swings. Level 1 played as a prologue, not
  a contest.

Sources: `SPEC.md` lines 151-173, `engine.py` lines 660-675,
`runs/narr5/result.json`, `runs/narr5/events.jsonl`.
Playtest date: 2026-11-06.
