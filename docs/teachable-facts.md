# Teachable facts for the game (research 2026-11-07)

Goal: a short list of true facts about Diocletian's Palace that
players leave with after a game. Each fact is tied to a mechanic,
a label, or a card.

Working rule: a fact sticks when play makes it happen, for
example the board flip. Labels at the moment of use come second.
End-of-game cards come last.

## Tier 1: taught by the game itself

### 1. The cellars mirror the palace above

The substructures under the south residential block copy the
floor plan of the imperial apartments. The apartments were
rebuilt over the centuries; the cellars survived. So the cellars
are the best evidence of the original plan.

Teaching device: print the Level 2 map on the back of the board,
mirrored, and flip the board at the countdown. Players see with
their hands that the level below copies the level above.

Honest note for the rulebook: the real cellars underlie only the
south apartments. The game mirrors the whole city board.

Source: Nomado Travel guide, "The Substructures of Diocletian's
Palace", official basements page.
https://www.nomadotravel.app/en/attractions/diocletians-cellars

### 2. Four gates, four rulers: the Tetrarchy

Diocletian split the empire among four rulers (two Augusti, two
Caesars), then built this palace as the home of the one who quit.
The game's four players entering four gates already embody this.

Say so in one rulebook line. Do not name seats after tetrarchs;
that pairing would be invented history. The gates carry metal
names instead (fact 3).

Source: Wikipedia, Diocletian. https://en.wikipedia.org/wiki/Diocletian

### 3. The gates are real and named for metals

- Golden Gate: north, the main land entrance, faces Salona the
  provincial capital.
- Silver Gate: east.
- Iron Gate: west.
- Bronze Gate: south, the sea entrance.

The Emperor already sits at the south gate in the measured rules.
In the real palace the Emperor lived at the sea gate: his
apartments lined the south wall. The game teaches a true thing by
accident; labeling the four gates makes it deliberate.

Bonus: the real Bronze Gate route climbed from the sea through
the cellars up to the Peristyle. The game's south-side approach,
with the retreat hall one step north, echoes that path.

Source: Wikipedia, Golden Gate (Diocletian's Palace).
https://en.wikipedia.org/wiki/Golden_Gate_(Diocletian%27s_Palace)

### 4. Cardo and decumanus

Roman towns and army camps were planned around a north-south
*cardo* and an east-west *decumanus* that meet at the forum. The
palace is half villa, half army camp. The game's streets cross at
the checkpoint, which is the Peristyle.

Teaching device: label the central east-west street "Decumanus"
and mark the checkpoint as the Peristyle. The Peristyle seal
already carries the name. Players leave knowing why Roman street
grids look the way they do.

Honest note: the physical board has two vertical streets; the
real palace has one cardo north of the Peristyle (D27, D33
history).

### 5. The emperor who yielded

Diocletian was the first Roman emperor to step down by choice
(1 May 305). The palace exists because of that decision.

Flavor device, no mechanic change: after the second clean
strike, the win text says the Emperor **yields the throne**
instead of "is defeated". He never dies in the game; he retires.

Cautions:

- He abdicated in Nicomedia, not here. Keep it as flavor, not
  reenactment.
- The cabbage quote ("if you saw the cabbages I grow, you would
  not ask me to return") comes down through later writers. Print
  it as "as the story goes".

Source: Wikipedia, Diocletian.

## Tier 2: fact cards at game over

- **The sphinx was as ancient to Diocletian as he is to us.**
  The black granite sphinx by the Peristyle was carved about
  1450 BC under Pharaoh Thutmose III. Diocletian imported it as
  an antique, about 1,750 years old. The palace is about 1,720
  years old today. The numbers nearly match; this is the fact
  players retell. Three sphinxes survive in Split.
- **The persecutor's tomb became the martyr's cathedral.** His
  octagonal mausoleum is now the Cathedral of Saint Domnius; by
  tradition Domnius was martyred in his persecution, 304. The
  Temple of Jupiter opposite became the Baptistery of St John.
  The two flank the Peristyle, like the game's two flanking seal
  sites.
  Source: https://www.famous-historic-buildings.org.uk/cathedral-of-st-domnius-split.html
- **People still live there.** The palace never became a ruin.
  Refugees settled inside the walls after Salona fell; about
  3,000 people live inside the palace today. UNESCO World
  Heritage since 1979. Closing line: "you just played inside a
  building where people still live."
  Sources: https://total-croatia-news.com/lifestyle/croatia-roman-palace
  https://whc.unesco.org/en/tentativelists/2015
- **The aqueduct still flows.** Diocletian's aqueduct brings
  water about 9 km from the Jadro spring. Restored in 1880, it
  still supplies Split.
  Source: https://en.wikipedia.org/wiki/Aqueduct_of_Diocletian
- **Roman soldier kit vocabulary (already shipped).** The six
  equipment cards teach pugio, pilum, galea, scutum, gladius,
  and lorica segmentata with one-line meanings. Keep; tighten
  the card wording.

## Cost to the measured design

None. Every item is presentation: print generator, web strings,
card text. No `rules_*.json` knob moves, so no new batches are
needed.

The board flip is a reflection. A reflection preserves every
distance, so the mirrored back page is graph-isomorphic to the
current board. Every measured number (timeouts, medians, gate
fairness) carries over exactly. The back must mirror all marks:
gates, sites, blocked cells. Optional test: assert that mirroring
the generated back data reproduces the front data.

## Recommended cut of five

1. Cellars mirror flip (back of the board).
2. Tetrarchy rulebook line.
3. Metal gate labels on the board.
4. Cardo and decumanus street labels.
5. "The Emperor yields" win text.

## Open questions

- Which facts does the designer pick for the final shortlist?
- Flip rule wording for the print pack: lift pawns, flip, drop on
  the same table spot (that spot is the mirrored cell).
- Does the web board mirror the grid with an animation at the
  level transition (app.js presentation only)?
- Does the pack get a game-over fact card page, or one fact card
  per player?
