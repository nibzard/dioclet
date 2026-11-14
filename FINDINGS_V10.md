# V0.10 findings: the big succession map

Date: 2026-11-14. All numbers are offline bot play from
`tools/v10_level2_experiment.py`: 1,536 games per arm on seeds
1030000+ (`results/v10-level2/confirm.json`), and the finalists again
on seeds 1040000+ (`results/v10-level2/holdout.json`). The full
tables and the method are in `notes/v10-level2-2026-11-14.md`. The
decision is D51. Spend: none (offline).

## Headline (holdout)

| Measure | 0.9.4 twin board | 0.10 big board |
|---|---|---|
| Succession map | 13 × 9 | 19 × 13, the palace size |
| Gate distance to the Peristyle | 4/6/4/6 | 9/9/9/9 |
| Factions | public, fixed | three cards and three blanks on six sites |
| Draws | .009 | .029 |
| Level 2 rounds p10 / median / p90 | 5 / 8 / 15 | 8 / 12 / 19 |
| Total median rounds | 23 | 27 |
| Gate win rates N/E/S/W | .275/.218/.262/.236 | .255/.236/.236/.245 |
| Gate uniformity p | .007 | .67 |
| Prestige farmer win share | .12 | .16 |

## What changed and why

- Level 2 was never too quick. No game in any arm ended it in 4
  rounds or fewer. The cards make it longer by making the support
  hunt longer, not by making the walk longer.
- 0.9.4 favours the north and south gates. At 384 games (D50) the
  gap was not visible. At 1,536 games it is significant in two
  independent seed sets.
- The big board equalizes the whole route: gate to the Peristyle,
  and gate to the cards. It is the only layout tested that passes
  uniformity in both runs with a spread under 2 points.

## Watch items

- Draws at 2 to 3%. These come from games that reach the level 2
  round cap.
- The first four-seat Haiku game (`runs/haiku-table-v010/`) found
  and searched the cards in round 1. All three factions were public
  after two rounds. Level 2 took 9 rounds. Prestige, not the cards,
  decided the endgame: no rival could afford to contest the winning
  claim. A faction dealt to a far corner site went unused.
- The print kit and the art show the big board (four A4 tiles, the
  same cut lines as the palace board) and six faction cards. The
  browser engine still plays the 0.9.4 succession map.

## The Prestige lockout (2026-11-14)

In the Haiku game every rival held 0 Prestige when the winning claim
was proclaimed, so nobody could pay the contest fee. Full numbers:
`notes/v10-prestige-2026-11-14.md`.

- Cheaper or longer contests make it worse. Free contests, no
  duel-loser cost, and a three-round window raise draws to 16–39%.
- Four guard posts on the succession map (`rules_v10_l2posts.json`)
  hold up on a 1,536-game holdout: draws 2.8% to 1.6%, the Prestige
  farmer .16 to .22, and gate fairness p = .51. With seats that spend
  on support during a rival's claim, the base board skews to the north
  gate (p = .0001); with posts it stays fair (p = .56).
- The posts do not change the share of claims that no rival can
  contest (about 2–3% for bots). The bots never reach the agents'
  all-zero state, so that part of the problem is how people play. The
  quick reference and the rulebook now say: keep 1 Prestige in reserve.
- Not adopted yet: the posts need a decision and a print-kit update.
