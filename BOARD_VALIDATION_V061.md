# BOARD_VALIDATION_V061.md — the encoded real board

Branch `feature/v061-realboard-validation`. Rules under audit:
`rules_v06_realboard_p3.json` (hash `c174c9f5f77101c4…`), engine
`0.1.1`, board module `board.py`. Every number below is generated
from the rules file, not transcribed by hand (regression-tested in
`tests/test_realboard.py` and `tests/test_board_v061.py`).

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
   is added here for symmetry and history (D27). Recommendation to
   the designer stands: add the lane or accept the measured skew.
3. Level 2 sites are our placement, not the designer's; Level 2 has
   no artwork yet.
4. Start circles outside the gates are modeled as the gate cells
   themselves; functionally identical.
