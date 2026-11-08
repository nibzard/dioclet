# Intervention plan: six blocks and imperial succession

Date: 2026-11-08.

Status: implemented and released as V0.8 (`rules_v08_succession.json`, contest fee 1 Prestige). The plan below is the design record; measured outcomes are in `FINDINGS_V08.md`.

## 1. Purpose

Make the game about preparing a credible claim to imperial power, securing support, and facing rival claimants.

The player should understand why each action matters:

- Equipment gives you lasting strength.
- Prestige lets you secure political support and strengthen a challenge.
- Support makes your claim credible.
- Rivals can stop your claim through direct play.

The game remains a four-player board game with two phases, six treasure locations, dice movement, and one action per turn.

## 2. Decisions and test values

| Subject | Direction | Initial prototype or remaining test |
| --- | --- | --- |
| Physical board | Six intact blocks; one card per block | Enforce this in the movement graph and both renderers |
| Main streets | Cardo north–south; decumanus east–west | Use existing streets; put the four gates at their ends |
| Starting gates | Assign players to gates randomly at setup | Seed the shuffle; offer manual assignment; rotate gates in repeat sessions |
| Treasure collection | Keep the equipment you collect | Remove free grants; allow collection in both phases |
| Empty treasure choice | Collect automatically when there is no competing action | Retain the existing modal for real alternatives |
| Glory | Give it the player-facing name Prestige | Test storage limits together with spending opportunities |
| Seals | Replace them with faction support | Support from two of three groups qualifies a claim |
| Faction rules | Use one acquisition rule | Visit the meeting place and spend one Prestige |
| Endgame | Replace attacks on Diocletian with a contested claim | Test the response-window rule below |
| Player endorsements | Do not require rivals to endorse a winner | Consider optional diplomacy only after the core loop works |
| Visual style | Square corners and even borders | Preserve keyboard access, mobile zoom, and visible action modals |

The initial Prestige cap of three and support cost of one are test values. The discussion establishes the design problems, not the correct final economy.

## 3. Correct the physical board first

### Required geometry

Use `rules_v073_sixblocks_cardo.json` as the source for generated board assets.

- The board has 19 columns and 13 rows.
- Six solid 5×5 blocks occupy the same six footprints.
- Streets follow the perimeter, columns 6 and 12, and row 6.
- Column 6 is the cardo. Column 12 is a secondary street.
- Row 6 is the decumanus.
- North and south gates are `(6, 0)` and `(6, 12)`.
- East and west gates are `(18, 6)` and `(0, 6)`.
- The main crossing and checkpoint are `(6, 6)`.

There are 150 blocked cells and 97 street spaces. Each block names its own district explicitly. No street passes through a block footprint.

V0.7.2 is rejected for the active board. Its added column 9 splits two blocks and creates eight physical blocks. Calling the separated pieces one building does not satisfy the layout requirement. Keep that rules file for historical replay and comparison.

### Geometry tradeoff

Six equal blocks in the existing three-column, two-row arrangement cannot also have a new central north–south street without dividing blocks. Use an existing street instead. The cardo is therefore off-center in this game map.

Gate-to-crossing distances are north 6, east 12, south 6, and west 6. These are geometry facts, not win probabilities. Do not describe the gates as equally strong. The layout is an abstraction that preserves street orientation and gate alignment; it is not an exact reconstruction of the palace.

### Layout acceptance

1. Count connected groups of blocked cells: exactly six, each containing 25 cells.
2. Require every declared footprint to equal one physical group.
3. Require one distinct, reachable treasure entry adjacent to each block.
4. Require continuous main streets and gates at their four ends.
5. Require the checkpoint at the main crossing and all street spaces connected.
6. Generate the browser board and print board from the same rules file.
7. Reject V0.7.2 under this contract, even though it declares six buildings.

Do not add or move streets to improve measured balance. Treat any further geometry proposal as a separate, visible design change.

## 4. Assign players to gates fairly

Random assignment shares the chance of receiving each gate. It does not remove a gate advantage within an individual game.

Separate player identity from gate identity. Configure four players first, with their names and human or bot policies. Then shuffle their gate assignments once. Display the result before the game begins.

Use a seed-derived stream dedicated to gate assignment. It must not consume the stream used for treasure placement, movement, or combat. Log the assignment and include it in replay data.

Offer a manual gate option for teaching, reproduction, and experiments. For repeated sessions, offer a four-game rotation in which each player uses every gate once. Keep starting-player order separate from gate assignment.

Acceptance: every player receives one distinct gate; the same seed and settings reproduce the assignment; names, colors, policies, and progress stay attached to the player. The interface must not label a player “North” after assigning that player to the east gate.

## 5. Make preparation matter

Remove the grant of missing equipment at phase transition and at the city timeout. Equipment remains with its collector for the whole game.

Keep the initial bonus tiers for comparison: zero to two items give +0, three to five give +1, and six give +2. Retain collection actions during the succession phase so a player can recover through play. Duplicate items give no extra bonus.

Keep the first complete set and checkpoint claim as the initial phase trigger. Finish the current round and one additional full round. The round limit still bounds the city phase. A timeout opens succession without manufacturing equipment.

For the first candidate, preserve pawn positions at transition. This keeps route planning meaningful. Compare that choice against returning pawns to their assigned gates in a separate experiment.

Keep the checkpoint reward initially at one Prestige and record any reward lost at the cap. Persistent equipment is the main reason to collect. Do not add several special rewards before testing that change.

Acceptance: a player with two items enters succession with two items, can collect the remaining four, and can still win. A player who collected six retains the stronger equipment bonus.

## 6. Replace seals with faction support

Use three simplified groups. These groups and the acquisition rule are game abstractions, not a documented Roman election procedure.

| Group | Meaning | Initial meeting place |
| --- | --- | --- |
| Army | Troops back your claim | District F, the barracks site |
| Imperial officials | Officials recognize your authority | The Peristyle crossing |
| City elites | Wealth and local connections support you | District A, a civic meeting site |

Use one rule: visit a group's meeting place and spend one Prestige to gain its support. No extra die roll is required. Gain at most one support per action. Each group can support each player once.

For the first prototype, support is permanent and available to all four players. Do not add exclusive banners, support theft, bidding, or forced player endorsements at the same time.

Make support available during both phases in the initial candidate. This supplies a useful spending action during preparation. Test availability only during succession as a separate variant.

When a treasure and a faction share a location, collection and gaining support are different actions. The action modal must show both. Automatic collection applies only when no competing action exists.

Acceptance: all groups use the same rule; repeated acquisition is rejected; no unsupported faction-specific roll thresholds remain. The player card shows named support, not unexplained C/B/P tokens.

## 7. Give Prestige useful spending choices

Use Prestige as the player-facing term for Glory. Preserve the old term in legacy replay data where required.

Start with the existing sources: successful guard duty, winning a duel, and the first checkpoint claim. Spend Prestige on support. Also test a declaration before a challenge: spend one Prestige for +2 on the attacker's roll. The cost is paid whether the challenge succeeds or fails. Do not add an interactive defender payment in this first version.

Use three storage variants: cap two, cap three, and no storage cap. Keep acquisition costs and rewards fixed across that comparison. Test early faction spending separately so a cap change is not confused with a new spending opportunity.

Measure rewards lost at the cap, turns with no useful reward available, spending, time spent farming, and whether saving dominates collection. A larger bank is not evidence of a better game.

## 8. Test a contested claim instead of a boss fight

Use this concrete first candidate:

1. During succession, reach the Peristyle with support from two different groups and use your action to proclaim a claim.
2. Give every other player one turn to respond after the proclamation.
3. A rival can challenge the claimant using the normal movement and duel-range rules.
4. A successful challenge cancels the claim and returns the claimant to the claimant's assigned gate. Equipment and support remain.
5. A failed challenge leaves the claim active. Leaving the Peristyle voluntarily cancels your claim.
6. If the claim survives all three responses, the claimant wins and is acclaimed emperor.

Only one claim can be pending. Another player must cancel it before making a new claim. A claimant whose turn occurs during the window can maintain the claim without moving. Challenges use the existing attacker-wins-ties convention initially.

Track responding player identities, not a generic round counter. Rotating the first player must not omit a rival or count the same rival twice. A completed response counts whether the rival challenges, moves, or takes another action. Failure to challenge is a valid response.

Keep a fixed succession deadline in the first candidate. If no claim succeeds, record a draw. Measure repeated cancellations before adding any additional ending rule.

This candidate replaces Emperor hit counters and the attack/retreat loop. It is a testable proposal, not a historical account of events in the palace. Evaluate it before making it the default public ruleset.

## 9. Keep the historical framing clear

Frame the game around rival claims after Diocletian's retirement. Explain that the Tetrarchy had two senior emperors and two junior emperors. Do not imply that four named tetrarchs entered four palace gates and fought Diocletian here.

Keep the real gate names: Golden north, Silver east, Bronze south, and Iron west. Keep the equipment names with short definitions. Label the cardo and decumanus where players use them.

Keep the cellars-mirror idea as a later presentation task. Mirroring must include gates, sites, block footprints, labels, and coordinates. It must not add streets or change movement distances.

Sources and historical limits are recorded in [teachable facts](teachable-facts.md) and [faction support](../notes/faction-support.md).

## 10. Implement in dependency order

| Work package | Main files | Completion condition |
| --- | --- | --- |
| A. Repair and freeze the board | New rules JSON; `board.py`; both board generators; board tests | Six physical blocks pass the layout contract; browser and print agree |
| B. Separate players and gates | Python and browser setup; seeded streams; observations; replay records | Seeded random assignment and manual assignment reproduce correctly |
| C. Persist equipment | Both engines; legal actions; phase transition; rules validation | No free grants; collection works in succession; old replays still work |
| D. Add faction support and Prestige | Both engines; configuration; observations; player cards | One support rule; explicit costs; shared availability; configurable cap |
| E. Add the claim window | Both engines; legal actions; victory checks; event logs | All three rivals receive a response; cancellation and victory are deterministic |
| F. Update policies and reporting | `policies.py`, `tactical_policy.py`, `web/bots.js`, `candidate_actions.py`, `report.py`, analysis tools | Bots understand the new goal; reports expose the new incentives |
| G. Update teaching and interface | Browser rulebook, setup, action modals, print generator, protocol | The same rules appear in every artifact; a new player can explain the loop |

Create a new V0.8 rules family and an explicit gameplay mode for succession. Extend schema validation and dispatch deliberately. Do not silently reinterpret old fields named `seals` or `emperor_hits`. Keep old rules, logs, and reports available for replay.

The new state needs public faction support, an optional pending claim, and the set of players who responded. Define corresponding legal actions and events. Keep hidden treasure identities out of observations and unopened-card choices.

Update policy descriptions and action shortlists so a legal winning claim or necessary response is never excluded. Version changed policies and record the version with each experiment.

## 11. Verify behavior and compare candidates

### Correctness checks

Cover board topology, gate assignment, persistent equipment, support costs, duplicate support, precommitted spending, claim cancellation, response order, timeout, stale actions, deterministic replay, and the visibility of hidden information.

Check both Python and JavaScript engines with the same recorded action sequences. Their random generators currently differ; use injected die sequences or a shared random specification before claiming seed-for-seed equivalence.

Browser checks must include desktop and phone layouts, an edge click on a treasure marker, automatic collection, competing actions in a modal, Cancel and Escape, keyboard focus, replay, and bot-only completion. Maintain square corners and even borders.

### Experimental sequence

1. Measure the corrected V0.7.3 board with the current mechanics as the control.
2. Compare persistent equipment against the control while holding other rules fixed.
3. Compare uniform faction support with the old seal prerequisite.
4. Compare the contested claim with the old ending, using the selected preparation and support rules.
5. Compare Prestige caps and early spending through a small factorial design.
6. Run the selected combined candidate against the control with policies appropriate to each ruleset.
7. Conduct human playtests focused on understanding, agency, waiting, and the ending.

Use paired seeds and all 24 player-to-gate permutations for gate-sensitive comparisons. Also rotate starting-player order independently. Include identical-policy games to separate a gate effect from a policy effect. Record draw rates as well as wins.

Start with offline bots. Expand sample sizes to resolve uncertainty; report confidence intervals and the actual number of games. Do not treat an old-board result as evidence for the corrected map. Live model tournaments are a separate budgeted task.

### Decision evidence

Report gate and policy win rates, rounds and turns, collection counts, support timing, Prestige earned/spent/wasted, first-collector outcomes, claim attempts, cancellations, responses, idle turns, and draws. Separate simulated observations from human feedback.

Agree on playtest acceptance targets before selecting the winner. At minimum, players must understand why collection helps, why Prestige matters, how support is earned, and how to stop a rival. A candidate that merely finishes is not sufficient.

## 12. Release and handoff

Publish the board correction independently of the gameplay redesign. It fixes the map while leaving a clear comparison baseline.

For V0.8, update the rulebook, quick reference, teaching script, feedback form, browser copy, and print components together. Remove obsolete seals, Emperor hits, and statements about free equipment from the new mode. Label legacy artifacts with their version.

Record the rules hash, layout hash, policy versions, experiment seeds, and measured limitations. Keep the previous deployment available for rollback. Publish the selected gameplay candidate after its checks and comparison are complete.

The remaining design choices are the Prestige cap, support timing, transition position reset, and whether the proposed response window produces a satisfying ending. The plan supplies starting candidates for each; experiments and human play decide the final values.
