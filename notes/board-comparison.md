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
