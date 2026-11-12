# Human playtest session 001

Date: 2026-11-12 (transcript received; session played shortly before).
Players: four (Dominik, Darija, Filip, one unnamed; Darija kept the
tracker). Base: the V0.8.1 print pack, played with live rule changes.
Source: a single speech-to-text transcript in Croatian, so individual
attributions and some numbers are uncertain; every claim below quotes
the audio. Three independent extractions cross-checked each reading.

Status of this record: observations only, per `protocol-v08.md`.
Interpretation is separated at the end and in FINDINGS notes.

## What was actually played

- Base V0.8.1: collect six equipment, first to six opens Level 2 at
  the Peristyle, everyone returns to their gate, factions give
  support for 1 Prestige, claim the throne, contest by duel,
  beaten claimant returns to their gate. Prestige cap 3 kept.
- **House rule, used all session**: duel bonuses split into attack
  and defense. Each weapon card gives +1 attack, each shield +1
  defense, **summed per side** (full set = +3 attack, +3 defense;
  partial sets like +2/+3 were computed live). An initial +5/+3
  reading was argued down to +3/+3.
- Duels as played: challenger pays 1 Prestige, attacker rolls first,
  each side adds its own bonus. Live duels: defender 8 vs challenger
  6 (claimant held the throne); challenger 5+2=7 vs claimant 6+3=9
  (claimant held). Rolls of 8 fit 2d6; one early line says "2d"
  ("To je difens i 2d"), but the engine uses one die, so the die
  count is uncertain from audio alone.
- They did not play the written two-supporter rule
  ("Ali ovdje kaže dva suportera. To sad nismo igrali"), keeping it
  as a difficulty variant.

## Level 2 was redesigned at the table

Adopted during play:

1. **New support cards**: six cards replace the (now useless)
   equipment cards on Level 2 — three open faction meeting places,
   three blind, shuffled randomly. Players hunt them for support.
   Verdict at the table: "To je najbolje" (best idea of the
   session).
2. **The Peristyle can never be a meeting place**, fixing the
   officials-on-Peristyle bug a player announced he would exploit:
   "Pa ću ja iskoristiti taj bug u igrici."
3. **Claim survival window**: a claim wins if it stands uncontested.
   One round was judged too short, two "is statistics"; they settled
   on three, with a late objection that three is a lot.
4. **Challenge radius**: a challenger must enter a three-step radius
   around the Peristyle, to be painted on the Level 2 board.
5. **Duel Prestige**: the loser is "shamed" and loses their own
   Prestige; the winner is paid 1 by the bank (played exactly once:
   "dobio 1 prestiža od tih iz banka").
6. **Smaller Level 2 board**: cut from six to four blocks; cardo and
   decumanus run gate to gate and cross at the goal "X" (the
   Peristyle) in the middle — kept partly because it teaches which
   street is which ("opet edukativno učiš šta je kardo, šta je deku
   manus").
7. **Meeting places equidistant from all gates** (one player sat 3
   steps from a meeting place, others needed 4-6).

Left open: Prestige sources on Level 2 (duels were the only one that
fired); whether the guard-post stars stay on the second map (the
transcript ends on this question); six factions instead of three;
whether a broke player is eliminated; the repeated-loss exploit.

## Observed problems (with quotes)

- **Level 2 Prestige drought**: "Ja ne mogu platiti prestiž da bi
  ušlo u [borbu]" — a zero-Prestige player is locked out of the
  core interaction; everyone can bleed out in one round.
- **Stacked bonuses made duels hopeless**: a defender facing +3
  stacks: "Sve jedno ću izgubiti. Šta god bacio ću izgubiti" — then
  conceded and went to his gate. Twice: "Ovo je nebalansirano /
  nije balansiran, ovo nije dobro."
- **Officials-on-Peristyle bug**: exploited live (confirmed in
  `rules_v08_succession.json`: officials [6,6] equals checkpoint
  [6,6]).
- **Kingmaking**: "Ja sam upravo tako iskoristio sad da te dobijem
  da ne dobiješ igru."
- **Positional exploit**: claiming near your own gate makes you
  unreachable ("jer sam ja blizu vrata, ne moš ti ništa"); Dominik
  counted 11 steps to arrive and needed maximum rolls.
- **Anti-contest meta**: after three losses nobody contests you any
  more because it no longer pays.
- **Level 1 orbits the rim**: "niko ne ide kroz sredinu... ploča te
  ne potiče da ideš kroz sredinu i svi kruže u krug."
- **Mandatory trigger feels like a burden**: the player who would
  finish the set must open the level and fight: "meni nema smisla
  da završim... Ne da mi se s njim boriti, di ću [biti] strategija."
- **Pacing**: "Malo dugo traje igra", "Želim samo završiti."
- **Bookkeeping**: attack/defense totals had to be recounted
  mid-duel; Darija had missed one player's bonus on the tracker.
- **Verdicts**: "Dobra igra" twice; "Nije loša igra, malo mi fadi
  [još]"; rated "50%, možda 60%" potential.

## Interpretation (analysis, not record)

Four findings at the table independently reproduce measured
simulation results — the humans ran, unaided, the same experiments
the harness ran:

1. **Stacking combat bonuses break duels.** Their +3/+3 full set is
   C1's failure mode (24.8% draws from stacked attack modifiers);
   their words "već je ispalo iz balansa" match the sim verdict.
   Their own principle — "treba zadržati uvijek jedan mehanizam po
   igri" — is the C2 rule (at most one equipment bonus per duel
   side). If the attack/defense split survives, it needs the same
   cap or a much smaller scale.
2. **Content placement drives movement and fairness.** "Nobody goes
   through the middle" is the V0.6 finding (placement moved balanced
   wins and timeouts more than most rule changes) and the V0.8
   east-gate skew (16% east, 12 steps to the crossing). Their
   request — "smodelirati više različite geometrije" — is a
   runnable harness sweep.
3. **Level 2's Prestige economy has no income.** The sim saw both
   sides of this coin: fee 0 caused denial loops (57% draws), fee 2
   removed live counterplay (zero contests in four live games,
   D38). The table hit the no-income side directly. Duel-wins-pay-1
   (which they improvised) is already the engine's rule; the open
   question is whether guard posts survive on map two.
4. **The claim window is a tuned knob, and humans tune it the way
   the harness does.** Their one/two/three-round debate is the
   `grace_full_rounds` sweep; the radius rule is a new, testable
   anti-orbiting, anti-kingmaking mechanism with no sim precedent.

One human-only finding the bots could never produce: **kingmaking
and the broke-player lockout**. Bots do not negotiate or hold
grudges; the repeated-loss exploit and the "attack so you don't
win" move are multiplayer-economy failures that only live play
surfaces. The radius-plus-window redesign is their answer; the
acclamation response model is the engine's current answer. Both
should be simulated, but social dynamics set a floor the harness
cannot measure.

Also: the first collector experienced the trigger as a burden even
though the sim shows first claimants win 44% of games. The
incentive exists; the experience reads as being made the target.
That gap between measured advantage and felt annoyance is worth
watching in the next session.

The blind support cards are a second, telling reinvention: the table
independently re-derived partial revelation (the B arm) for Level 2
and called it the best idea of the session — while the bots priced
B as inert. Hidden placement that humans can reason about is worth
more than the harness can measure.

## What this session answers from protocol-v08.md

- Q3 (claim dramatic or frustrating): frustrating — the claim
  system was rebuilt mid-session (window, radius, fee).
- Q5 (ordinary duels on purpose): yes, once duels became the only
  Level 2 Prestige source.
- Q6 (gate asymmetry): deeper version found — nobody crosses the
  middle; meeting-place distances unequal (3 vs 4-6 steps).
- Q7 (rule causing most questions): the Level 2 Prestige economy
  (who pays whom, how to earn any), plus duel-bonus bookkeeping.

Positive-evidence test (state the goal, name a choice, want another
game): partially met — players stated the goal, made real choices
(the whole redesign), but "want another game" is not on tape;
verdicts hover at 50-60%.
