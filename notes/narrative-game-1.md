> **Engine caveat:** this game ran before the emperor-miss retreat
> bug was fixed (the miss-retreat to `[2,3]` was overwritten; see
> FINDINGS.md §6). Impressions that the retreat penalty "never
> fired" trace to that bug, not to the rules. Other observations
> stand.

# Narrative playtest 1 — seed 4101, run `runs/narr1`

Date: 2026-11-06. Table of four: Ana the trader (P0), Brutus the veteran (P1),
Cassia the scholar (P2), Drusus the wanderer (P3). One turn at a time via the
CLI; no state file was opened.

## Outcome

- Winner: **P2 Cassia the scholar**, `end_reason: emperor`, two hits on turn
  55 (level 2, round 5). Length: 14 rounds, 55 turns (level 1: 9 rounds /
  36 turns, level 2: 5 rounds / 19 turns). `comeback_win: true`; the First
  Challenger (P1) did not win. Glory spent: P0 and P2 spent 2 each, P1 spent
  1, P3 held 0 all game.

## Observations a counter cannot capture

- **The table never drew a blade.** Zero duels in 55 turns. Once everyone
  holds the same equipment tier, a duel is a coin flip the defender wins on
  ties, while a guard post pays the same Glory with no downside. Brutus, our
  duel-happy veteran, found no fight that met his own "even odds" bar once
  the tie rule was priced in. The duel list (25 to 34 options per turn) was
  noise we scrolled past every single time.
- **Brutus's barracks curse was the emotional peak of act one.** Twice in a
  row he rolled 1 against the guard's 6 (identical scores both times). The
  table groaned out loud; he "adapted" by paying his Glory at the peristyle.
  Dice spite created a better story than any mechanic did.
- **The finish was genuinely tense.** Ana hit first (paid Glory, 8 vs 4),
  Cassia hit next (a natural 6). Both stood at one hit inside the chamber.
  Ana swung first on turn 52, rolled a 1, and missed; Cassia rolled 4
  against the Emperor's 1 and took the crown. Seat order, not skill, broke
  the tie — we talked about that for a while afterward.
- **The retreat rule never fired (engine bug).** Ana's miss logged
  `retreat_to: [2, 3]`, but the pawn stayed at `[2, 4]` and could re-attack
  stationary next turn. In `engine.py` the final
  `if tuple(me["pos"]) != dest` block overwrites the retreat position with
  the action destination. The miss penalty the SPEC promises does not exist,
  so the endgame is a no-cost dice race.
- **The level 1 to 2 transition was a wet firework.** All four of us held
  full kits a full round before Brutus triggered the checkpoint, so
  `auto_equip_at_transition` granted nothing and the "catch-up" was
  invisible. The two grace rounds were pure guard-post farming; nobody raced,
  nobody dueled, and the reveal felt administrative.
- **Turns 33 to 35 felt pointless.** Kits full, posts out of die range,
  positions about to reset. Cassia literally said "position resets anyway"
  and moved one step for no reason. Those turns should either be cut or given
  something to fight over.
- **Glory is a two-tier currency and the poor stay poor.** Ana (2 Glory)
  bought a guaranteed seal and a +2 Emperor swing — first blood. Drusus (0
  Glory) ground the peristyle at 1-in-3, missed three times, and never
  reached the throne room. He was spectating by round 4 of level 2.
- **Perfect information killed the checkpoint drama.** The progress panel
  lists `players_with_full_equipment`, so we all knew Brutus would trigger
  two turns before he did. Nothing to hide, nothing to bluff.

## Open questions

- Should a failed Emperor attack cost position (fix the retreat overwrite),
  or is free re-attacking the intended pacing?
- Can we make duels worth their rules text when all bonuses are equal?
- Is there anything for trailing players to do in the grace rounds?
