# BOARD_VALIDATION_V061.md — the encoded real board

Branch `feature/v061-realboard-validation`. Rules under audit:
`rules_v06_realboard_p3.json` (hash `c174c9f5f77101c4…`), engine
`0.1.1`, board module `board.py`. Every number below is generated
from the rules file, not transcribed by hand (regression-tested in
`tests/test_realboard.py` and `tests/test_board_v061.py`).

> **Superseded by V0.7 (2026-11-07).** The cardo was removed after
> the designer's correction: the physical board has six blocks, one
> card per block, and the simulated central street split the middle
> column into four strips (D33). This file stays as the V0.6 audit.
> The adopted board is `rules_v07_6blocks.json`; the V0.7 section
> at the end records the current facts.

## Provenance: what is confirmed and what is chosen

| Element | Source |
|---|---|
| Four gates at the middle of each wall; start circles outside them | Designer confirmed (2026-11-07) |
| Six city blocks with one entry circle each; stop on the entry to take the card | Designer confirmed |
| Board artwork, wall, six blocks, street network | Designer's board description |
| Building interiors blocked; 19 by 13 grid; 107 street spaces | Experimental encoding of the description |
| Entry cells on north street (2), south street (2), cardo (2) | Experimental (D31, measured; the physical board's blue circles sit differently and produced 44/44 gate skew) |
| Central north-south street (cardo) and checkpoint at the center crossing | Experimental (D27), grounded in the real palace plan |
| Glory posts near the four corners of the west and east edges | Experimental (D28) |
| Cellars, Barracks, Peristyle, Emperor chamber, retreat positions | Experimental (D31); Level 2 is not drawn on the physical board. These placements are **not claimed to be physically authentic**; they are the measured, symmetric choice |

Unverified against artwork (no image comparison performed in this
cycle): exact space counts per street segment versus the printed
board; whether the printed board has a cardo; the exact positions of
the blue entry circles; gate and card artwork details. The encoding
follows the written board description of 2026-11-07.

## Counts and reachability

- Grid 19 by 13 = 247 cells; 140 blocked building cells; 107 street
  spaces. Matches the intended encoding exactly.
- From every gate, all 107 street spaces are reachable. No special
  square is blocked; the validator rejects that (`engine.validate_rules`).
- Street degree: gates 3, checkpoint 4 (a crossing), cardo entries 2,
  edge entries 2, guard posts 2, retreat 2, Emperor 3.

## The map

`G` gate · `A–F` equipment entries · `X` checkpoint (Peristyle in
Level 2) · `*` Glory post · `c` Cellars (shares entry A) · `b`
Barracks (shares entry F) · `p` Peristyle (shares the checkpoint) ·
`E` Emperor (shares the south gate) · `r` retreat · `.` street ·
`#` building block.

```
       x=0    1      2      3      4      5      6      7      8      9     10     11     12     13     14     15     16     17     18
y= 0   .      .      .     [cA]    .      .      .      .      .     [G]     .      .      .      .      .     [C]     .      .      .
y= 1   .      #      #      #      #      #      .      #      #      .      #      #      .      #      #      #      #      #      .
y= 2  [*]     #      #      #      #      #      .      #      #      .      #      #      .      #      #      #      #      #     [*]
y= 3   .      #      #      #      #      #      .      #      #     [B]     #      #      .      #      #      #      #      #      .
y= 4   .      #      #      #      #      #      .      #      #      .      #      #      .      #      #      #      #      #      .
y= 5   .      #      #      #      #      #      .      #      #      .      #      #      .      #      #      #      #      #      .
y= 6  [G]     .      .      .      .      .      .      .      .     [pX]    .      .      .      .      .      .      .      .     [G]
y= 7   .      #      #      #      #      #      .      #      #      .      #      #      .      #      #      #      #      #      .
y= 8   .      #      #      #      #      #      .      #      #      .      #      #      .      #      #      #      #      #      .
y= 9   .      #      #      #      #      #      .      #      #     [E]     #      #      .      #      #      #      #      #      .
y=10  [*]     #      #      #      #      #      .      #      #      .      #      #      .      #      #      #      #      #     [*]
y=11   .      #      #      #      #      #      .      #      #     [r]     #      #      .      #      #      #      #      #      .
y=12   .      .      .     [D]     .      .      .      .      .     [E]     .      .      .      .      .     [bF]    .      .      .
```

The Emperor chamber `[E]` at `[9,12]` is the south gate cell (P2's
start), exactly as in every earlier version of the game.

## Key distances (shortest street paths)

| From \ To | A (Cellars) | B | C | D | E | F (Barracks) | Checkpoint | Emperor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| North gate P0 | 6 | 3 | 6 | 18 | 9 | 18 | 6 | 12 |
| East gate P1 | 21 | 12 | 9 | 21 | 12 | 9 | 9 | 15 |
| South gate P2 | 18 | 9 | 18 | 6 | 3 | 6 | 6 | 0 |
| West gate P3 | 9 | 12 | 21 | 9 | 12 | 21 | 9 | 15 |

Properties worth noting:

- The checkpoint is 6 steps from the north and south gates and 9
  from the east and west gates: the board is a rectangle, so no
  single cell is equidistant from all four gates. Measured first-
  challenger rates are nonetheless equal (181/152/175/152 in the
  V0.6 baseline).
- The retreat `[9,11]` is 1 step from the Emperor chamber.
- Cellars, Barracks, and Peristyle form a triangle (northwest,
  southeast, center); every gate has one near site and one far site.

## Shortcuts, alternative routes, determinism

- No path crosses a building: `Board.neighbors` never returns a
  blocked cell, and BFS distances therefore never include one. The
  property test `test_blocked_cells_are_never_reachable` walks all
  140 blocked cells against a full distance map from every gate.
- Alternative equal-length routes exist (for example north gate to
  Cellars `[9,0] → [3,0]`: west or east around the ring is not equal,
  but west gate to checkpoint can run along the decumanus or dip
  through the cardo at equal cost when detouring). When routes tie,
  the engine walks north, then east, then south, then west. This
  changes the drawn path, not distances or outcomes; random-vs-random
  fairness (23/24/22/23) confirms no outcome bias from it.
- Movement, duels, and duels of range are all computed on the same
  street graph, so duel range 2 means two street spaces, never a
  shortcut over a building.
- Sample games from every V0.6 batch replay byte-identically
  (`replay --verify`); 116 automated tests pass at the audited
  commit.

## Differences from the physical board, summarized

1. The physical board's blue entry circles sit on the west and east
   streets; the encoding spreads entries (north street, south street,
   cardo) because the described placement handed those gates 44% win
   share each (D31).
2. The cardo does not appear on the printed board as described; it
   was added here for symmetry and history (D27). The designer
   resolved the open recommendation on 2026-11-07: no cardo, the
   six-block structure governs (D33; see the V0.7 section).
3. Level 2 sites are our placement, not the designer's; Level 2 has
   no artwork yet.
4. Start circles outside the gates are modeled as the gate cells
   themselves; functionally identical.

## V0.7: the six-block board (current, 2026-11-07)

Rules: `rules_v07_6blocks.json`. The cardo (street column x=9) is
removed. Streets are the perimeter, two internal vertical streets
(x=6, x=12), and one central east-west street (y=6): 150 blocked
cells form six 5x5 blocks, 97 street spaces. One block, one card:
entries A `[3,0]`, B `[7,0]`, C `[15,0]` on the north street, D
`[3,12]`, E `[11,12]`, F `[15,12]` on the south street. B and E are
a 180-degree rotation pair in front of the middle blocks; the
retreat hall is `[10,12]`, one step east of the Emperor, because
`[9,11]` now sits inside a block. Everything else is unchanged from
the V0.6 audit above (gates, checkpoint `[9,6]`, glory posts, seal
triangle, 2d6 movement).

```
        x=0        6         12        18
y=0     · · A · · · B · n · · · C · · ·      n,e,s,w = gates
y=1..5  · ##### · ##### · ##### ·           A-F = card entries
y=2     * ##### · ##### · ##### *           X = checkpoint
y=6     w · · · · · · · X · · · · · · · e   * = guard posts
y=7..11 · ##### · ##### · ##### ·           # = building block
y=10    * ##### · ##### · ##### *
y=12    · · D · · · · · s · E · · · F · ·
```

Distances from each gate (BFS on the street graph):

| From | Checkpoint | Card tour sum | Cellars | Barracks | Peristyle | Best two seals | Emperor |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 north | 12 | 66 | 6 | 18 | 12 | 18 | 18 |
| P1 east | 9 | 90 | 21 | 9 | 9 | 18 | 15 |
| P2 south | 12 | 66 | 18 | 6 | 12 | 18 | 0 |
| P3 west | 9 | 90 | 9 | 21 | 9 | 18 | 15 |

The tension is explicit and symmetric: north and south gates hold
the shorter card tour, east and west gates the shorter checkpoint
walk, and the cheapest two-seal tour costs the same from every
gate. Measured consequences (1000 games, seeds 1000-1999): Level 1
timeouts 129 (V0.6: 162), median 24 total rounds, 5.70 collected,
70% comebacks, first challenger 199/245/215/212 by gate, balanced_se
mirror 25.1/22.1/25.2/27.6, random x4 mirror 211/178/204/208 wins
with 199 draws (V0.6 random was 23/24/22/23: the same even band).
Regression tests:
`tests/test_board_v061.py` (counts, six 5x5 blocks, distances,
tour sums, reachability).

### V0.7.1 correction: doors on the streets

Designer correction (2026-11-07, D34): gates must open onto streets,
as in the real palace. North gate `[12,0]` tops the east vertical
street; south gate `[6,12]` foots the west vertical street (a
180-degree rotation pair); the Emperor keeps the south gate and the
retreat hall is one step north, `[6,11]`. Distances per gate:
checkpoint 9/9/9/9, card tour 66/90/66/90, cheapest two seals
18 everywhere. Measured: Level 1 timeouts 121 per 1,000 (V0.7:
129), median 23 rounds, 70% comebacks, first challenger
240/223/221/195, balanced_se mirror 24.2/28.2/25.5/22.1, random x4
19.9/21.9/19.1/22.4. Tests: `tests/test_board_v061.py` (gates on
street columns, all gates 9 from the checkpoint, Emperor and
retreat placement).
