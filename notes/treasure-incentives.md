# Treasure collection incentives

Research date: 2026-11-08.

Sources: [Original transition specification](../SPEC.md), [browser engine](../web/engine.js), and [browser rulebook](../web/rules.js).

## Verified findings

- The original specification calls free equipment a catch-up rule to test, not a settled design.
- The first player with six items who claims the checkpoint earns one Glory, subject to the cap of two.
- The claim triggers the transition after the grace round. A round limit also triggers transition.
- Collected equipment improves duels during the city phase: three items give +1 and six give +2.
- At transition, every player receives every missing item. Everyone returns to their own gate.
- Collection and position advantages therefore do not persist into the palace phase. Glory persists.

## Design interpretation

The rule keeps players competitive after the city phase. It weakens the collection race by making the full set free at transition. Depending on the board and opponents, gaining Glory while another player completes the set can be a reasonable strategy. This is an incentive analysis, not a new measured comparison of policies.

## Open questions

- Does the designer want a collection race or a shared preparation phase?
- Should collected equipment persist without free grants, with missing items still available during the palace phase?
- What reward should the first collector receive, particularly when already at the Glory cap?

No game rules change as part of this review.

## Glory cap review, 2026-11-08

Sources: [V0.2 experiments](../FINDINGS_V02.md), [browser rulebook](../web/rules.js), and [narrative game five](narrative-game-5.md).

A cap limits stored bonuses and creates a choice between a guaranteed seal and boosted Emperor attacks. This is a design interpretation; the reviewed sources do not establish why two is the uniquely appropriate limit. Both purchases cost one Glory. Glory has no spending option during the city phase, so players at the cap cannot convert further wins or the checkpoint reward into stored value.

The older V0.2 cap-three experiment reports 7.01 duels per game versus 5.80 at baseline, with the aggressive policy still winning 6%. This result concerns fixed bots on an older board. It does not prove that a cap of two gives the best human experience. Narrative simulations also recorded idle turns at the cap; these are not human playtests.

The cap and free equipment interact: once a player has two Glory, neither more Glory nor collecting equipment for the palace necessarily provides a lasting reward. Review these incentives together before selecting a new cap. No rule changes are applied.
