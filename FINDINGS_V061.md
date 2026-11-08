# FINDINGS_V061.md — real board validation and family playability

Branch `feature/v061-realboard-validation`, base `3daa2a8`, engine
`0.1.1`, primary rules `rules_v06_realboard_p3.json` (hash
`c174c9f5f77101c4…`). Bots frozen (D24) except the explicitly
versioned `balanced_se` probe (D32). All experiments offline and
free; every batch is 1,000 games on seeds 1000–1999 (200 games,
seeds 3000–3199, for the instrumented turn-level run) under the SPEC
§13 schedule. 124 automated tests pass; sample games from V0.3,
V0.5, and V0.6 batches replay byte-identically on the current code.

## 1. Is the board correctly represented?

Yes, as an encoding of the written board description. Counts,
reachability, degrees, distances, and the no-shortcut property are
regression-tested; the full audit with map and distance matrix is
`BOARD_VALIDATION_V061.md`. Three placements are the design team's
measured choices, not the designer's artwork: entry spread, cardo
with central checkpoint, and the seal triangle. Level 2 has no
artwork yet; nothing here claims physical authenticity for it.

## 2. Is 2d6 the right movement system?

Yes. Full comparison, same seeds and schedule:

| Movement | L1 timeouts | Median rounds | p90 | Collected | Auto-granted | Duels | Comebacks |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1d6 | 939 | 34 | 38 | 4.02 | 1.98 | 9.7 | 5% |
| 1d8 | 569 | 32 | 37 | 5.19 | 0.81 | 9.2 | 33% |
| 1d10 | 341 | 30 | 34 | 5.52 | 0.48 | 8.6 | 51% |
| 1d12 (new) | 90 | 27 | 32 | 5.65 | 0.34 | 8.1 | 68% |
| **2d6 (adopted)** | **162** | **26** | **32** | **5.71** | **0.29** | **8.1** | **68%** |

1d12 trims timeouts further (its flat tail rolls 10+ more often than
2d6), but it needs a specialty die, is harder for children to read,
and the gain is 7 points of timeout rate. 2d6 uses two ordinary
dice, gives a familiar bell curve, and lands mid-band on duration.
**Recommendation: keep 2d6 for movement, one die for all fights and
trials.**

## 3. Does the game finish in a satisfying time?

Median 26 rounds, p90 32, no Level 2 timeouts in 1,000 games. Two
numbers frame the human question:

- **Walking share: 48.1% of turns are pure movement** (200-game
  instrumented run; the small board measured 4.6%). Median use is 4
  steps of an average-7 roll.
- **Event cadence: the median gap between eventful turns anywhere on
  the board is 1 turn**; someone takes a card, stands a post, duels,
  or claims something on almost every consecutive turn. First
  treasure lands at median global turn 4.

So the game is busy globally but each player walks about every other
own turn. Whether that reads as pleasant racing or dead time is now
strictly a table question; the simulator cannot answer it.

## 4. Are the four gates balanced?

The board is fair; the skew was in the bots. Four mirror
experiments, 1,000 games each:

| Agents (all four seats) | P0 | P1 | P2 | P3 |
|---|---:|---:|---:|---:|
| random × 4 (frozen) | 23 | 24 | 22 | 23 |
| tactical × 4 (frozen) | 33 | 13 | 17 | 37 |
| balanced_se × 4 (D32 probe, ties to southeast) | 29 | 24 | 28 | 19 |
| mixed experiment schedule (frozen bots) | 31 | 16 | 21 | 32 |

Reading: agents with no directional preference (random) split the
gates evenly, so the geometry is sound. The frozen scripted agents
break ties toward the northwest (coordinate ordering in their
destination ranking), and the balanced_se probe flips the skew with
it (P3 40→19, P1 13→24 in the balanced mirror class). The gate skew
is therefore an artifact of frozen-bot tie-breaking, amplified by a
107-space board where equidistant choices are common. Humans and
reasoning players show no such fixed direction.

Turn-order position within a round keeps a real edge for the acting
first player (30/27/24/19 in the tactical mirror), consistent with
the known final-round initiative effect; the rotating start already
spreads it across seats.

## 5. The Level 1 round limit, revisited

Claimed city phases run median 17, p90 21, max 24 rounds; 16% of
games time out at the cap of 24. Raising the cap to 28 (new arm)
rescues only 26 of those 162 games, leaves the median unchanged,
and extends the worst-case session by four rounds. Timed-out games
are unlucky treasure spreads, not systematic inefficiency: overall
collection is 5.71 of 6 with 0.29 auto-granted.

**Recommendation: keep the cap at 24.** It bounds the session; the
residual timeouts are the designed safety valve (the gate opens and
everyone moves up with free gear). Revisit only if playtests report
feeling rushed.

## 6. AI tournament status

Prepared, not run: no live spending was authorized this cycle.
`tournaments/v061_realboard_ai.json` holds 16 mirror plus 16
rotation games under a $0.75 aggregate guard. The built-in estimator
(1,296 calls, $0.15) underestimates this board: measured turn counts
give roughly 190 calls per mirror game and 48 per rotation seat,
about 3,800 calls; at the measured payload of roughly 530 tokens
per shortlist (median 16 candidates from a median of 29 legal
actions, cap always respected, no mandatory action ever dropped),
the realistic estimate is **$0.30 to $0.35**. Runs when authorized.

## 7. Simplicity assessment

Full scorecard: `PLAYABILITY_SCORECARD_V061.md`. In short: the
teaching script is eight sentences; the rules carry three
exceptions; no powers, no phases, no elimination, no lost turns.
The one accessibility risk is the 48% walking share, and the one
depth gap is the old one: a duel cannot slow a leader. Per the
brief, neither is touched by a new mechanic in this cycle; the
leader-bounty experiment stays queued as its own future arm.

## 8. Limitations and unverified assumptions

- No human has played the print pack. All feel statements are
  predictions, marked as such everywhere.
- Level 2 placements and the cardo are our choices; the physical
  board has neither confirmed.
- The instrumented run uses 200 games; turn-level medians are stable
  at that n, tails are not.
- Bot tie-breaking artifacts mean scripted gate rates should not be
  quoted as human fairness numbers; use the random-mirror and
  balanced_se-flip evidence instead.

## 9. Prioritized plan for physical playtesting

1. Print `playtest/playtest-pack.html` (board, cards, tokens,
   rulebook, quick reference, teaching script, feedback form).
2. Run the four protocol groups in `playtest/protocol.md`
   (children 6–9, one family, adult gamers, older adults).
3. Record the eleven observations per session; never edit
   predictions into recorded fields.
4. Feed the forms back into the next design cycle; the two decisions
   waiting on humans are walking-share feel and Level 1 tail feel.

## 10. Recommended next ruleset

`rules_v06_realboard_p3.json` as-is: real board, entry spread, seal
triangle, cardo checkpoint, 2d6 movement, city cap 24, everything
else the adopted V0.3/V0.5 package. No rule changes this cycle; the
game that goes to the table is the game this repository measured.

## Reproduce

```bash
python3 -m unittest discover -s tests            # 124 tests
python3 sim.py batch --rules rules_v06_realboard_p3.json --games 1000 \
  --seed-base 1000 --schedule experiment --out results/v06_realboard_p3
python3 tools/mirror_batch.py --rules rules_v06_realboard_p3.json \
  --games 1000 --seed-base 1000 --out results/v061_tactical_mirror
python3 sim.py tournament --config tournaments/v061_realboard_ai.json \
  --out results/v061_ai --dry-run                 # live run needs authorization
python3 tools/make_print_pack.py                  # regenerates the pack
```

## 11. V0.7 addendum: the six-block board

After this report was written the designer corrected the encoding
(D33): the point of the layout is six blocks, one card per block,
and the simulated cardo split the middle column into four strips.
V0.7 removes the cardo (97 street spaces, entries B and E moved to
the north and south streets, retreat one step east of the Emperor).
Every conclusion above survives, and two improve: city timeouts drop
from 162 to 129 per 1000 games, so the round-24 cap has more headroom,
and gate balance holds (balanced_se mirror 25.1/22.1/25.2/27.6; the
frozen-schedule skew stays the D32 tie-break artifact). The
recommended table ruleset moved through `rules_v07_6blocks.json` and
`rules_v071_realgates.json` and settled at `rules_v072_cardo.json`
(the real two-street plan; game-identical to the V0.6 p3 ruleset
this report measured, so every number above applies unchanged).
