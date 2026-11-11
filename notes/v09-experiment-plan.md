# V0.9 design experiment: treasure identity

Status: complete. Results: [FINDINGS_V09](../FINDINGS_V09.md),
`results/v09-design-001/` (C1, superseded) and
`results/v09-design-002/` (C2, the simplified set the same
direction produced after review; recommended). Approved design experiment (user direction,
2026-11-11). Outside the programme.md mutation space by design: programme.md
forbids equipment powers inside hyperparameter search and requires a separate
approved experiment for them. This note is that experiment.

Research date: 2026-11-11.

Sources: user design direction (2026-11-11), [V0.8 findings](../FINDINGS_V08.md),
[treasure incentives note](treasure-incentives.md), [V0.8 rules](../rules_v08_succession.json).

## Goal

Test whether giving the six treasures distinct identities changes routing,
combat, and gate fairness. The principle: every equipment card should make a
player reconsider their next move.

## Arms

All three arms use matched seeds and the same seat schedule (24 gate
permutations, four probe profiles). Fresh seed base 300000. This range is
outside every burned range (tests 4000-4007, classic 1000, screens 20000,
holdouts 90000-92000, live 130000/140000, autoresearch 200000/400000/600000).

- **A — baseline**: `rules_v08_succession.json` unchanged.
- **B — partial revelation**: `rules_v09_reveal2.json`. Two randomly selected
  districts' equipment are public from the start. Exploration still reveals.
- **C — distinct abilities plus revelation**: `rules_v09_abilities.json`.
  Adds the six abilities below and zeroes the count-based combat tiers
  (abilities replace tiers, they do not stack). Checkpoint still needs six
  items; the three-item checkpoint rule is a separate later experiment.

Ability table (values are data, so balancing means editing numbers):

| Item | Ability | Effect |
|---|---|---|
| gladius | `attack_bonus` | +1 attack roll in duels |
| scutum | `defense_bonus` | +1 defense roll in duels |
| pilum | `attack_vs_claimant` | +1 attack when dueling the pending claimant |
| pugio | `first_duel_win_prestige` | +1 Prestige on first duel win |
| galea | `private_inspect` | once per game, privately inspect one unexplored district |
| lorica_segmentata | `prevent_displacement` | once per game, stay in place after losing a duel as claimant |

## Interpretation decisions to record in DECISIONS.md

- V0.8 succession has exactly one displacement: a claimant who loses a challenge
  duel returns to their gate (succession.py:436-439). Lorica therefore protects
  only a claim holder. The claim is still cancelled; only the position reset is
  prevented. The broader reading has no mechanic to attach to in V0.8.
- Start reveals draw from the `equipment` RNG stream after the district shuffle.
  That stream is used nowhere else, so on matched seeds arms A, B, and C share
  identical boards, district mappings, gates, turn order, and movement dice.
- Start reveals are recorded in `state["revealed"]` (public from turn one) and
  in a `state["setup_reveals"]` list. They do not emit turn records, because
  every record in `state["events"]` must keep the turn-record shape that
  replay and result() rely on.
- Galea inspection: the event logs player, ability, and district, but never the
  item (D17 information boundary). The item reaches only the inspecting
  player's observation through a viewer-scoped field.
- Policies gain a frozen per-profile item-preference table (applied identically
  in all arms) so that revealed item identity can influence routing. Without
  it, arm B would measure only the existing revealed-vs-hidden preference.

## Metrics

- Gate win rates P0..P3 with Wilson intervals (baseline skew: north 34%, west
  25%, south 19%, east 16% at fee 1).
- Strategy win rates per profile.
- Route diversity: share of first explores aimed at start-revealed districts;
  count of distinct first-explore districts per game; first-explore district
  entropy across the batch.
- Ability usage: games with at least one use, per ability; pugio awards; lorica
  saves; galea inspections; pilum boosts.
- Equipment versus victory: per-item hold rate among winners versus losers.
- Draws, median rounds, first-challenger wins (regression check).

## Size

480 games per arm (20 gate-permutation blocks; 120 games per gate per arm).
Noise floor at 96 games per arm is about 12 points for strategy rates; 480
gives Wilson half-widths near 8 points per gate cell.

## Out of scope

- The three-equipment checkpoint rule (separate follow-up experiment).
- Browser (web/) JavaScript parity. The parity suites gate a release, not a
  design trial; parity work happens only if V0.9 is promoted.
