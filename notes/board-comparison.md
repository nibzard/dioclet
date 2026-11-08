# Board comparison: designer board vs simulated board

Research date: 2026-11-07. Sources: the designer's board description
(relayed by the user, 2026-11-07), `SPEC.md` §3, `rules_baseline.json`,
`DECISIONS.md`.

## Short answer

The simulator is a deliberate compression of this exact board, not a
copy of it. SPEC §3 was written from the same images ("a small graph
abstraction of the six zones, four gates, and central junction in the
provided images") and states the plan openly: "the 5×5 graph is
deliberately smaller than the number of white circles on the real
board... A later version should use an extracted adjacency graph of
the actual printed paths once the game loop proves worthwhile."

The topology matches. The geometry does not, and two differences
could change measured results.

## What matches

| Board feature (designer) | Simulated as |
|---|---|
| Four gates at N/E/S/W wall midpoints | Gates P0 north, P1 east, P2 south, P3 west |
| Colored circles just outside each gate (blue N, red W, yellow E, green S) | Player starts on their gate cell; equivalent role |
| Six neighborhoods, 3 columns by 2 rows, streets never enter them | Districts A–F at the six pane positions |
| One face-down card per neighborhood | Shuffled hidden treasure per district, revealed on first explore |
| Outer perimeter loop of spaces | Border cells of the 5×5 grid |
| One central horizontal street, W gate to E gate | Row y=2, from (0,2) through (2,2) to (4,2) |
| Two internal vertical streets, top to bottom | Interior column connectivity |
| Orthogonal movement only, no diagonals | Same |
| Strong overall symmetry; building variety is scenery | Ignored as scenery, correctly |

## What differs, and why

1. **Scale.** The board has roughly 90 spaces (about 18 along an
   edge, 12 down). The simulation has 25, in a square, roughly a
   3.5-to-1 compression of a 3-to-2 rectangle. Reason: SPEC §3 chose
   a first-pass mechanics test, with real-graph extraction deferred.
2. **Districts are nodes vs blocks.** In the simulation a district is
   one cell you stand on. On the board, a district is a solid block
   with a card; players move on streets around it. Same intent,
   different geometry. The physical version needs a convention:
   does exploring happen from a space next to the card, or on a
   marked card space?
3. **Checkpoint position.** The simulation puts the checkpoint at the
   exact center (2,2), equidistant from all four gates. The board's
   purple marker sits at the RIGHT internal intersection, east of the
   board center, closer to the east gate. This is the difference most
   likely to change results: the measured gate fairness (all gates
   within ±3%) rests on the central placement. If the purple circle
   is the checkpoint (or the Peristyle, which shares the center cell
   in the simulation), the east seat gets a shorter first claim.
4. **Glory posts.** The simulation has four, on the left and right
   edges between gates and corners. The board shows pale blue circles
   on the left and right edges AND on the internal vertical streets,
   function unknown. If these are the Glory spaces, the count and
   spread differ.
5. **Level 2 sites have no visible home.** The simulation reuses city
   cells: Cellars in the northwest district, Barracks in the
   northeast, Peristyle at the center, Emperor chamber at the south
   gate, retreat one step north of it. The board description shows
   none of these except possibly the purple circle. The six cards or
   the blue circles may be intended for this role. Needs the
   designer's mapping.
6. **Outside start spaces** exist on the board; the simulation has
   none. Cosmetic.
7. **Larger intersection spaces** in the digital render have no
   simulated counterpart. Cosmetic unless they are special.

## What transfers and what needs re-measuring

Transfers (rule-internal, independent of board size): attacker-tie
fairness, grace-round effect, rotating start, Glory cap 2 verdict,
Peristyle cost 1 verdict, auto-grant role, the core open problem
(a duel pays only its winner), AI guard-post blind spot.

Needs re-measuring on the true graph: game length in rounds, duel
frequency (range 2 covers far less of a 90-space board), first-claim
rate, comeback rate, gate fairness (especially with an off-center
checkpoint), the stall tail, seal-trip lengths, and any
displacement-style geometry verdict.

## Open questions for the designer

1. What is the purple circle: checkpoint, Peristyle, or something
   else? If a checkpoint, why the right intersection rather than a
   spot equidistant from all gates?
2. What are the blue circles: Glory or guard-post spaces, event
   spaces, or Level 2 sites?
3. Where do the Cellars, Barracks, Emperor chamber, and retreat hall
   sit in Level 2? Do the six cards flip or move?
4. Are the four colored circles outside the gates the player start
   positions?
5. Approximately how many spaces separate: a gate and the nearest
   intersection, the two intersections, and an intersection and the
   nearest district card? (Needed to re-tune the movement die and
   duel range.)

## Next step

Extract the printed path graph (about 90 nodes) into the rules JSON
and re-run the free 1,000-game baselines plus one 32-game AI check
(about $0.09) to confirm the adopted package still holds. The engine
board is rules-driven; the change is a taller grid with building
cells blocked, or a custom edge list, plus re-tuned movement knobs.
SPEC §3 scheduled exactly this once the game loop proved worthwhile;
the V0.5 verdict is that point.

## V0.6 measured results (2026-11-07)

The real board now exists in the simulator: 19 by 13 with 140
blocked building cells, 107 street spaces, gates and sites per
D26–D31. Every arm below is 1,000 games, seeds 1000–1999, SPEC §13
schedule, versus `results/v03_base` (25 spaces).

| Arm | L1 timeouts | Median rounds | Collected | Auto | Duels | Gate wins P0/P1/P2/P3 | Comebacks |
|---|---:|---:|---:|---:|---:|---|---:|
| small board (v03) | 0 | 14 | 5.62 | 0.39 | 4.6 | 27/26/24/23 | 70% |
| real, d6, entries on W/E streets | 939 | 34 | 4.02 | 1.98 | 9.7 | 6/44/5/44 | 5% |
| real, d8, same | 569 | 32 | 5.19 | 0.81 | 9.2 | 8/40/9/43 | 33% |
| real, d10, same | 341 | 30 | 5.52 | 0.48 | 8.6 | 12/34/12/42 | 51% |
| real, d10, entries N/S/cardo | 340 | 31 | 5.67 | 0.33 | 8.9 | 32/13/16/40 | 49% |
| real, 2d6, entries N/S/cardo | 162 | 27 | 5.71 | 0.29 | 8.2 | 30/17/20/34 | 68% |
| real, 2d6, seal triangle (p3) | 162 | 26 | 5.71 | 0.29 | 8.1 | 31/16/21/32 | 68% |
| p3, random vs random | n/a | 39 | n/a | n/a | n/a | **23/24/22/23** | n/a |

Findings so far:

1. **Single d6 movement cannot finish the city phase on the real
   board** (94% timeouts, 4.0 of 6 collected). The user's 2d6
   proposal fixes pacing: 162 timeouts, median 27 rounds (mid-band),
   5.71 collected, comebacks 68%.
2. **Content placement is a fairness lever as strong as any rule.**
   Entries on the west/east streets (as described on the physical
   board) hand those gates 44% each. Spread entries (north street,
   south street, cardo) equalize the first-challenger race
   (181/152/175/152), but clustering both roll-seal sites on the
   north street then hands north the Level 2 travel race (32%).
   The seal triangle (cellars northwest, barracks southeast,
   peristyle center) is the tested fix.
3. First-challenger equality is the cheap diagnostic: it isolates
   Level 1 placement; remaining skew then lives in Level 2 geometry.
4. **The residual gate skew is a bot artifact, not a board flaw.**
   Random-vs-random on the final board (p3) gives 23/24/22/23 per
   gate: the geometry is fair. The 31/16/21/32 skew under the
   experiment schedule comes from the frozen bots resolving every
   equidistant choice toward the northwest (engine path tie-break
   north-east-south-west, policy destination sorting by coordinate).
   On 25 spaces these ties were harmless; on 107 they snowball.
   Reasoning players and humans do not share this bias; an AI
   tournament on p3 (about $0.09) would confirm.

## V0.7 measured results: the six-block correction (2026-11-07)

The designer corrected the encoding: the board has six blocks and
one card per block; the point of the layout. The V0.6 cardo (D27)
split the middle column into four strips and left entries B and E
on a street that does not exist on the physical board. V0.7
(`rules_v07_6blocks.json`) removes the cardo and moves B to the
north street `[7,0]`, E to the south street `[11,12]`, and the
retreat hall to `[10,12]`. Same 1000-game protocol as the table
above, seeds 1000-1999:

| Arm | L1 timeouts | Median rounds | Collected | Auto | Duels | Gate wins P0/P1/P2/P3 | Comebacks |
|---|---:|---:|---:|---:|---:|---|---:|
| six blocks, 2d6 (v07) | 129 | 24 | 5.70 | 0.30 | 6.5 | 37/15/26/22 | 70% |
| eight blocks, 2d6 (p3) | 162 | 26 | 5.71 | 0.29 | 8.1 | 31/16/21/32 | 68% |

- Pacing improves: fewer timeouts and two rounds faster at the
  median, with identical collection and comeback rates.
- The frozen-schedule gate split stays skewed northwest-plus; the
  balanced_se mirror on the six-block board reads
  25.1/22.1/25.2/27.6 and first challenger 199/245/215/212, so the
  geometry is even and the skew is the D32 tie-break artifact. The
  random x4 mirror agrees: 211/178/204/208 wins, 199 draws, the
  same band as the V0.6 random result (23/24/22/23).
- The board's tension is now explicit and symmetric: north/south
  gates hold the shorter card tour (distance sum 66 versus 90),
  east/west gates the shorter checkpoint walk (9 versus 12), and
  the cheapest two-seal tour costs 18 from every gate.

## V0.7.1: the doors move onto the streets (2026-11-07)

Second designer correction: the north and south doors open onto
vertical streets, as in the real palace. North gate to the top of
the east vertical street `[12,0]`, south gate (Emperor and retreat
with it) to the foot of the west vertical street `[6,12]`, retreat
one step north `[6,11]`. Same protocol, seeds 1000-1999:

| Arm | L1 timeouts | Median | Collected | Comebacks | Gate wins P0/P1/P2/P3 |
|---|---:|---:|---:|---:|---|
| v071 scheduled | 121 | 23 | 5.66 | 70% | 29.5/19.6/20.9/30.0 |
| v071 balanced_se x4 | n/a | n/a | n/a | n/a | 24.2/28.2/25.5/22.1 |
| v071 random x4 | n/a | n/a | n/a | n/a | 19.9/21.9/19.1/22.4 (167 draws) |

- Every gate is now exactly 9 spaces from the checkpoint; the
  card-tour sums (66 north/south, 90 east/west) and the two-seal
  tour (18 everywhere) carry over unchanged.
- Both fairness probes sit in the same even band as V0.7; the
  frozen-schedule spread tightened from 37/15/26/22 to
  29.5/19.6/20.9/30.

## V0.7.2: the real two-street plan (2026-11-08)

Third designer correction: the real palace has cardo and decumanus,
and the four doors sit at their ends, symmetric. V0.7.2 restores the
cardo and puts the north and south doors at its ends. The
six-buildings rule stands: the two middle buildings are declared as
single blocks pierced by the cardo lane, one card each at entries
B `[9,3]` and E `[9,9]`. Game content equals the V0.6 p3 ruleset
(100 paired games verified identical), so its measurements carry
over: 162 city timeouts per 1,000, median 26 rounds (18 city, 8
palace), 5.71 collected, 68% comebacks, first challenger
181/152/175/152, random x4 mirror 23/24/22/23, balanced_se probe
flips the schedule skew as in D32. The trade versus V0.7/V0.7.1
(121 to 129 timeouts, 23 to 24 median rounds) buys board fidelity:
the real street plan with symmetric doors, exactly as the palace
stands in Split.

## V0.7.3 correction: six physical blocks, 2026-11-08

Source: the designer's correction in this session; `rules_v073_sixblocks_cardo.json`; the movement graph in `board.py`.

V0.7.2 has eight connected groups of blocked cells. Its six declared building labels do not preserve six physical blocks. It is rejected as the active layout. Old V0.6 measurements cannot justify that mismatch.

V0.7.3 restores six solid 5×5 blocks and 97 street spaces. The cardo uses existing column 6 and the decumanus uses row 6. North and south gates both end column 6. East and west gates both end row 6. Column 12 stays as the secondary street. Each block explicitly owns one district; entries B and E return to the north and south perimeter streets.

The checkpoint sits at `(6,6)`. Distances from north/east/south/west are 6/12/6/6. Treasure-entry distance sums are 66/90/66/90. These values describe routes; they do not establish gate win rates.

Random player-to-gate assignment can distribute access fairly across games, but cannot equalize positions within a game. The [intervention plan](../docs/intervention-plan.md) specifies a seeded gate shuffle, manual assignment for experiments, and a rotation for repeated sessions.

Open questions: gate win rates on the corrected map, the effect of random assignment, and the interaction with the proposed faction-support economy. Existing historical reports remain unchanged. New measurements must name the corrected layout and rules hash.
