# Rules elegance and minimalism — research notes

Research date: 2026-11-13. Angle: when does a rule deserve to exist?
All quotes below were verified against the fetched pages on this date.

## Sources and verified quotes

### Reiner Knizia

- AndHeGames interview (Dec 2014):
  https://andhegames.com/how-reiner-knizia-makes-games
  - "I try to make games with very few principles, so they're natural
    to play."
  - "Once you understand the basic principles, you can almost derive
    what to do in various situations."
  - "I would very much bring it down to its bones – its essentials."
  - On condensing: "you've got to be careful that you don't lose the
    theme as you condense the rules."
- Opinionated Gamers interview, Andrea Ligabue (Apr 2011):
  https://opinionatedgamers.com/2011/04/12/the-art-of-design-interviews-to-game-designers-6-%E2%80%93-reiner-knizia/
  - "I am certainly a scientist who reduces redundancy by condensing
    the game into a few fundamental core principles."
  - "I am not an epic story teller who creates redundancy in the world
    by inventing ever more complexity through detailed rules."
  - Tradeoff admitted: reduction makes games "easy to access" but
    "somewhat abstract as a consequence of this reduction process."

### Depth vs complexity

- Daniel Piechnick, "The Depth: Complexity Ratio":
  https://daniel.games/the-depth-complexity-ratio
  - "Design your game not just for maximum depth, but also for minimum
    complexity."
  - Complexity is "a kind of money you can spend"; the ratio is not
    linear — "more complex games and elements must be vastly better
    than the simpler ones."
  - "Strategic depth should come from the interaction of many simple
    parts."
  - "90% of the abilities/spaces/cards etc. that you come up with
    would be fine, except that they're too complicated."
- Daniel Piechnick, "Reducing Complexity":
  https://daniel.games/reducing-complexity
  - "Your game is three times too complex."
  - "Find things in your game that work in similar ways, and make them
    work the same way."
  - "Never add a rule, in order to fix a problem" — fix with
    components inside existing rules instead.
  - Late-design audit: "can I possibly remove this
    text/icon/concept/rule?"
  - "You can usually make something half as complex, but 90% as good."
  - "If it's more than one sentence, it's probably too complicated."
  - "A bad designer simply lets out their belt, and adds complexity."
- Dan Felder, "Design 101: Complexity vs. Depth" (May 2015):
  https://danfelder.net/2015/05/21/design-101-complexity-vs-depth
  - Three axes: comprehension complexity, tracking complexity, depth
    ("how difficult it is to figure out the best possible move").
  - "Complexity is like a budget for your game design."
  - "It's much easier to add complexity if needed than it is to remove
    it later."
- Oliver Kinne, "The Deep Blue – depth in board games" (Aug 2022):
  https://tabletopgamesblog.com/2022/08/23/the-deep-blue-depth-in-board-games-topic-discussion/
  - Depth = the decision tree of choices per turn.
  - "While game depth is in principle a type of complexity, not all
    complexity leads to game depth."
  - Good deep games guide novices to "one or two" obvious options while
    experts find hidden routes.
- Bushnell's Law (attribution thin, treat as aspiration):
  https://en.wikipedia.org/wiki/Bushnell%27s_Law
  - "All the best games are easy to learn and difficult to master."

### Go / chess reference points

- Joshua Galecki, "Game Design Perspective: Go" (May 2021):
  https://www.pixelatedplaygrounds.com/sidequests/game-design-perspective-go
  - "Nothing about life and death and edges and corners is found in
    the rules of Go" — eyes, aji, corner openings are emergent.
  - "Go only has a single type of piece"; strength comes from
    arrangement of equal stones.
- Rosewater (below) on chess: "doesn't get more skillful if you add in
  four new piece types and double the size of the board."

### Complexity budgeting in a published game

- Mark Rosewater, "New World Order" (Dec 2011):
  https://magic.wizards.com/en/news/making-magic/new-world-order-2011-12-05
  - "If a common card is complex, it has to have a reason; it has to
    serve a purpose."
  - Complexity types: comprehension, board, strategic. "Comprehension
    complexity and board complexity are a problem for beginners.
    Strategic complexity is not... beginners can't see strategic
    complexity."
  - Goal: "not to remove complexity, but to shift where it is
    positioned."

### Sirlin

- "Designing Yomi" (2014): https://www.sirlin.net/articles/designing-yomi
  - "focusing on just what I needed to make the game work, and
    removing everything else that I could."
  - "it would have been natural to give each character at least 15
    different abilities, but I chose to limit it to just 3 or 4."
  - Depth preserved by payoffs that are "extremely difficult to
    compare or even to compute."
- "Balancing Multiplayer Games, Part 3" (2014):
  https://www.sirlin.net/articles/balancing-multiplayer-games-part-3-fairness
  - "Self-balancing forces fix balance problems without us having to
    know exactly what those problems even are."

### Mechanism taxonomy

- Engelstein & Shalev, "Building Blocks of Tabletop Game Design"
  (CRC/Routledge, 2nd ed. 2022):
  https://www.routledge.com/Building-Blocks-of-Tabletop-Game-Design-An-Encyclopedia-of-Mechanisms/Engelstein-Shalev/p/book/9781032015811
  - PAXsims review by Rex Brynen (Aug 2019):
    https://paxsims.wordpress.com/2019/08/14/review-building-blocks-of-tabletop-game-design/
    — 194 mechanisms in 13 categories; each entry gives strengths,
    weaknesses, and game consequences.

### Teach time

- Christian Strain, "Teaching a Game", League of Gamemakers (Jul 2014):
  https://www.leagueofgamemakers.com/teaching-a-game/
  - "A journey is so much easier to explain if you give the
    destination first." State the win condition "in only one
    sentence," then explain turns from the player's perspective.

## Mapping to Dioclet V0.9 (observed from FINDINGS_V09.md)

- The inert challenge-radius knob (no decision impact once duel range
  covers it) is the textbook rule that failed "earn its place" — cut.
- C2's "at most one equipment bonus per duel side" is Piechnick's
  merge principle: promote the shared exception into one global rule.
- Shame (loser pays 1 Prestige) is not a targeted patch; it is a
  systemic drain, closer to Sirlin's self-balancing forces — it
  removed a whole recycling loop (16.7% draws to 1.8%) without
  enumerating cases.
- Blind support being unreachable for model players inside 24 rounds
  is Rosewater's lesson in reverse: depth players cannot find is dead
  complexity weight.
- Open question: can the level-2 win condition (contest a claim that
  survives a two-round window) be stated in one sentence? Strain's
  test says the teachability of the endgame is the constraint.

## Open questions

- Does any published 4-player game combine a set-collection race into
  a king-of-the-hill endgame with a currency? (Comparable-games
  angle, not covered here.)
- Is there measured evidence anywhere on rules-count vs teach-time
  correlation (BGG weight vs rules pages)? Not verified this pass.
