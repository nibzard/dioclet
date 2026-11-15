# FINDINGS_V03.md — duel consequence experiments

Four batches, 1,000 games each, seeds 1000–1999, same SPEC §13
schedule, frozen bot policies (D24). The base for every variant is
`rules_v03_base.json` — the adopted V0.2 package (attacker wins duel
ties, grace 1, rotating first player). Each variant flips exactly one
duel-consequence knob. Result files: `results/v03_base`,
`v03_theft`, `v03_displacement`, `v03_lostturn`.

| Metric | V0.1 baseline | V0.3 base | theft | displacement | lost turn |
|---|---:|---:|---:|---:|---:|
| Median rounds | 15 | 14 | 15 | 14 | 15 |
| Median turns | 59 | 55 | 57 | 55 | 57 |
| Duels per game | 5.80 | 4.57 | 9.16 | 4.63 | 4.29 |
| Attacker win rate | 38% | 56% | 55% | 56% | 56% |
| Aggressive seat wins | 6% | 11% | **0.0%** | 11% | **14%** |
| Greedy seat wins | 19% | 26% | **36%** | 26% | 27% |
| Balanced seat wins | 31% | 29% | 30% | 29% | 28% |
| Random seat wins | 4% | 3% | 3% | 4% | 4% |
| Seat 1 / seat 4 wins | 30/19 | 28/21 | 27/23 | 29/20 | 29/20 |
| First challenger wins | 39% | 30% | 36% | 31% | 31% |
| Comeback share | 61% | 70% | 64% | 69% | 69% |
| Collected per player | 5.57 | 5.62 | 5.07 | 5.62 | 5.44 |
| Auto-granted per player | 0.43 | 0.39 | 0.93 | 0.38 | 0.56 |
| Glory wasted at cap | 0.46 | 0.24 | 0.00 | 0.25 | 0.19 |
| Draws | 0 | 0 | 0 | 0 | 0 |

New counters (see `summary.json: duel_consequences`): theft moved
2,671 Glory between players; displacement produced 4.63 kicks and
0.11 chamber evictions per game; the lost turn consumed 3.91 turns
per game.

## The V0.3 base package is healthy

Compared with the V0.1 baseline, the adopted package (ties →
attacker, grace 1, rotation) shortens games slightly (median 14
rounds), raises comebacks to 70%, cuts the first-challenger edge to
30%, narrows the seat gap to 28/21, and drops wasted Glory to 0.24
per player. Aggressive seats hold 11%. No new timeouts.

## 1. Glory theft backfires (`combat.duel_glory_theft`)

The most counter-intuitive result of the study. Duels double to 9.16
per game and Glory stops being wasted at the cap (0.00) — the
economy circulates perfectly. But the `aggressive` policy collapsed
to **0 wins in 500 seat-games** (95% CI 0.0–0.7%), while `greedy`,
which never duels, soared to 36%. Two mechanisms:

- A duel against a Glory-empty victim now pays nothing, and the
  aggressor frequently fights empty or weaker-paying targets.
- Every duel hands the winner fuel taken from a rival; the players
  who opt out of the bloodbath keep their tokens and win the Glory
  war by pacifism.

Under frozen bots, zero-sum Glory transfer punishes exactly the
strategy it was meant to reward. Rejected for V0.4 unless the theft
is supplemented by a small bank reward, which is a different
experiment.

## 2. Displacement to the retreat node is a doorstep teleport

Counters barely move (aggressive 11%, median 14 rounds, no draws)
because the drop point is the design flaw. The interference playtest
(`runs/narr8`, `notes/narrative-game-8.md`) falsified the mechanic
directly:

- The retreat node `[2,3]` is one step from the Emperor chamber, so
  evicting a player from the chamber delivers them to its doorstep.
  The playtest's door-guarder refused to kick a two-seal rival for
  exactly that reason. Chamber evictions did occur (108 across 1,000
  games) and cost the victim almost nothing.
- Losing a duel became win-win: baiting kicks turned provocation
  into free transport. Displacement delayed zero Emperor attempts.
- Displacements inside the Level 1 grace window are erased by the
  transition's gate reset, so four of seven kicks in the playtest
  cost nothing at all.

The rule produced the busiest, most interactive board of any game so
far — and none of the interaction contested the win. The fix
direction is geometry, not removal: drop the loser at their **own
gate**, or make the attacker push them one step (attacker chooses
direction, loser keeps agency). Both are single knobs for V0.4.

## 3. The lost turn is the only consequence with teeth

`combat.duel_lost_turn` consumes 3.91 turns per game, lifts
`aggressive` to **14%** (its best result anywhere; CI about 11–18%),
keeps `balanced` at 28%, lengthens the median game by one round, and
produces zero draws. Losing a duel now costs tempo — the one resource
the race actually spends. It is the adopt candidate of V0.3, with one
caution from the playtest series: a lost turn is the harshest
feeling consequence for children, and it should be playtested with
the personas (and eventually people) before it becomes permanent.

## Scorecard

| Target (from the V0.2 brief) | Status |
|---|---|
| Attacker wins 45–55% of matched duels | Met (55–56%, V0.3 base) |
| Aggressive sometimes succeeds | Closer: 14% with lost turn; still under balanced's 28% |
| No overwhelming turn-order advantage | Held at 28/21 (rotation) |
| A meaningful Level 2 interference move | Half met: lost turn delays; displacement's geometry must be fixed first |
| Collection feels worthwhile | Met (5.4–5.6 collected, 0.4–0.6 auto-granted) |

## Recommended next steps

1. Adopt `rules_v03_lostturn.json` as the V0.3 candidate; run the
   persona playtests on it before freezing.
2. V0.4 displacement geometry: loser returns to their own gate
   (`combat.duel_displacement_target: "gate"`), then attacker-push.
3. If theft returns, test `theft + 1 bank Glory` so empty victims
   still pay something.
4. The residual seat gap (28/21) and the `balanced` dominance
   (28–30%) remain the open structural questions; serpentine turn
   order is the untested lever.

## Reproduce

```bash
for v in base theft displacement lostturn; do
  python3 sim.py batch --rules rules_v03_$v.json --games 1000 \
    --seed-base 1000 --schedule experiment --out results/v03_$v
done
python3 compare.py results/v01_baseline results/v03_*
```
