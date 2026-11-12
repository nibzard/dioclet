# V0.9 simplification study

Research date: 2026-11-13.

Sources: web research across four angles (rules elegance theory,
comparable published games, streamlining case studies, economy and
hidden-information design; full citations below and in
`notes/rules-elegance-research-2026-11-13.md`), the repository's
own ~32,000 simulated games, the 2026-11-12 human session, and the
live OpenAI Decisions probes.

## What the design literature says (verified)

- **Complexity is a budget.** Depth should come from many simple
  parts interacting, not from detailed rules; assume most of your
  rules are too complicated (Piechnick, daniel.games). Knizia:
  build from few principles so play is derivable; he "reduces
  redundancy by condensing" rather than adding story rules.
- **Cut comprehension and tracking complexity, never strategic
  complexity** - beginners cannot even see strategic complexity
  (Rosewater, New World Order).
- **Never add a rule to fix a problem**; fix inside existing rules
  (Piechnick). A rule earns its place only if it changes a real
  decision, and earns it twice if it does systemic work.
- **Judge mechanics by payoff, not input** (Eric Lang). Our
  payoffs: the hidden-card reveal, the duel gamble, the contested
  throne.
- **Death spirals**: loser-pays rules drain the same fuel that
  funds retaliation, but bounded loser costs with an income floor
  are legitimate (Baker's thread; Kemet and Blood Rage split loss
  across position and recycled value). Every seat must keep a
  priced move or kingmaking follows (Pulsipher via Skeleton Code
  Machine; Wehrle's GDC defense of kingmaking).
- **Hidden information stays fair when symmetric and
  revealed-on-action** (poker model; Engelstein's information
  horizons). Hidden-but-distant (our blind support sites) fails -
  published guidance and our live probes agree.
- **Streamlining case studies** (Pax Pamir 2e, TI4, Through the
  Ages, My Little Scythe, Jaws of the Lion): cut tracking systems
  and card-specific text into type-level rules; keep the engine;
  use play data for numeric rebalance, not new systems.

## Screens (96 matched seeds each, gates from the climb)

| Candidate | Verdict | Evidence |
|---|---|---|
| S1 collapse six abilities to 3 attack / 3 defense, summed | rejected | healthy flow but strategy spread widens (collector 0.39, farmer 0.10; compounds to farmer 0.08 with trims) - the six identities are doing balance work |
| S2 drop the challenge boost (+2 for 1 Prestige) | adopted | metrics identical to incumbent; the boost is never the deciding choice under window+shame |
| S3 drop the contest fee | rejected | 60% draws, 24 claims per game - the denial loop returns even with window+shame; the fee does systemic work (reconfirms D38) |
| S4 drop the first-challenger Prestige bonus | adopted | healthy; removes a salad source and an incentive line |
| S24 = S2 + S4 | adopted | 384-game confirmation: 1 draw, median 24, 4.62 claims and 3.62 cancellations per game, tightest spread measured (0.138-0.326) |

## The rule ledger for v0.9.1 (`rules_v091_succession.json`)

Cut (two lines, zero measured cost):

- The optional duel boost (pay 1 Prestige for +2).
- The first-challenger checkpoint bonus.

Kept, each with its evidence:

- **Guard posts** - cut pressure exists ("a rule that just ticks")
  but they are the income floor that keeps zero-Prestige players
  alive as participants, not walking-dead kingmakers (live probe
  and playtest evidence, plus the engagement literature).
- **Contest fee 1** - S3's catastrophic screen; without it the
  denial loop returns regardless of window and shame.
- **Six distinct one-line abilities** - S1's spread damage; the
  identities carry balance, exactly the playtest's original
  intent.
- **Claim window 2 + loser shame** - the integrated
  stability/instability balance point (1.8% draws, 2.7
  cancellations per game, 13-17% free crowns).
- **Prestige cap 3** - bounds all loops cheaply; waste tracking
  is engine-side bookkeeping, not player-facing.

Net player-facing rules: about 23 down from 25, and the Prestige
economy now has two sources (duel wins, guard posts) and two
sinks (support, contest fee) plus the bounded shame cost - inside
the two-currency guidance and out of point-salad territory.

## The V1.0 direction (research-backed, too big for a trial)

The Pax Pamir 2e playbook: halve the rules by making state
board-readable and consolidating into one action system. Concrete
candidates, in rough order of promise:

1. **Equipment cards as the action system** (Concordia): the card
   you play is your action; holding it is your score. Collapses
   movement, powers, and part of the economy into one deck.
2. **Movement as combat** (En Garde): the pips you move are the
   strike you make; deletes the separate duel-resolution layer
   while keeping spacing and timing.
3. **Board-derived standings** (Pax Pamir, El Grande): support
   and threat read from positions and revealed districts, not
   tracked counters.
4. **Opponent-priced costs** (San Marco split-and-choose; Camel
   Up leg betting) replacing fixed fees where a table of rivals
   balances better than a tuned number.
5. **Dual victory clocks** (A Game of Thrones): the window plus a
   fixed final-round scoring, killing stall outright.

Each is a new design experiment in the programme.md sense and
needs its own plan note before any trial.
