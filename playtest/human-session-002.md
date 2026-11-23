# Human playtest session 002 — the Luka session

Date: transcript received 2026-11-18; play date not on tape, shortly
before.
Players: four at the board — Dominik and Filip (session-001
returners), Luka (new player, the youngest, taught live), and one
female voice (probably Darija: "Ja sam bila na bronze gate"). A
fifth person is heard once ("Teta ili Luka?"); the group around the
table changed during play. The teaching voice is not always the
same speaker.
Base: the V0.10.2 rules as written, with the deltas listed below.
Source: one speech-to-text transcript in Croatian
(`game-luka.md`, supplied outside the repo). The audio is heavily
garbled; one section repeats the same sentence ten times
("Ako izgubiš tu, vratiš se. Nije strašno."). Attribution and
numbers are uncertain; every claim below quotes the tape verbatim
(STT spelling kept). No timer, tracker, or feedback-form data came
with the session, so the timed fields of `protocol.md` stay empty.

Status of this record: observations only, per `protocol.md`
(V0.10.2 round). Interpretation is separated at the end.

## What was actually played

Close to the written JSON in structure; this group did not redesign
the game at the table the way session 001 did, though several
individual rules drifted in play (see deltas below).

- Two-dice movement with early stop, taught first and understood:
  "ne moraš četri, možeš se makniti tri i dva, bilo koji broj, do
  četri."
- Six items open the way to the Peristyle: "cilj igrati je skupiti
  oklop… kad skupiš 6 možeš otići na peristil i reći. Ja sam prvi."
  One more round is played after the first arrival: "A, ne, još
  jedan kruglje, sad mi odigravamo."
- Duel range two, optional for the mover, one attack per turn:
  "možeš borit' sa svima koji su u krugu dvaj kri", "Može odabrati
  se neće boriti sa mene", "Ne muš' dva napada."
- Equipment abilities as taught and used:
  - pugio wins ties, with both-holders cancellation noted right
    after: "kad je jednak broj kockica… Ja uvijek ću pobjeliti" /
    "A šta ako bojiti je u buđu je samo to kensela. Imaš isti moći
    kensela."
  - gladius +1 attack: "ti daje +1 u napadu."
  - scutum +1 defense: "To je 1 u obrani… koristiš u bilo kojoj
    situaci."
  - lorica prevents displacement for a beaten claimant: "Ali
    iskoristio haloriku i ostaje."
  - pilum pitched as Level-2 power: "To ti je koplje. Znači, na
    drugom nivo ti je isto bitno" — though questioned mid-game as
    making little sense without stacking (see Observed problems).
  - galea was played off-rules as a private Level-2 faction peek
    (see Deltas below).
- Succession as written: faction cards three factions plus three
  empty streets ("Prazna ulica", "Oficials", "elite bogataži",
  "Armija"); pay one at the card space ("I sada on mora platiti
  jedan novčić… ulaz u ulicu"); two factions needed ("moraš
  ostigurati podušku dvije skupile"); claim window two rounds
  ("moraš preživi dva kruga bez da te mi sruši"); one claim at a
  time ("Ne možete sad tvrditi, car, jer ono već sad tvrdio"); a
  beaten claimant returns to their gate, an ordinary duel loser
  does not ("Ideš nazad jedina ako si ove tvrdila da si cara… Ali
  u običnom dvojboju ništa").
- Contest fee vs ordinary duel: when one player said "Dobro, moram
  platiti jedan da može boriti", another immediately distinguished
  a free ordinary duel: "Je, ali se može dvoboj običnih s tobom
  napraviti."
- Prestige cap three, enforced mid-game when a player gained a
  fourth coin ("I sad ja imam četvrti noćič i šta ću ja? Moram ga
  vrati u bolu") and visible at the end ("Vidi tada imam tri
  ropčića").

## Deltas and uncertain readings

- **Galea played as a private Level-2 faction scout.** In V0.10.2
  (`reveal_district`), the galea is a once-per-game Palace action
  that publicly reveals one face-down treasure card. At this table
  it was taught as private ("pogledati ali samo on je vidio"),
  phrased as at-will ("možeš pogledati bilo kao u karticu. Kada
  godačeš", though later treated as spent: "Galea ti je bila danos
  pogleda kartolna, viša ne triber"), and saved on purpose for
  Level-2 faction cards ("ovo čuvaš za drugi nivo", "To bi dobro
  dođe dobra galeva", "I sada će on iskoristiti to i pogledat će…
  Evo, da, vidiš, tu to znači armi").
- **Duel Prestige moved directly from loser to winner.** In V0.10.2
  the winner earns 1 Prestige from the bank and the loser pays 1 to
  the bank (so beating a zero-Prestige rival still pays +1). On
  tape, coins transferred directly from the loser ("Sad dobijem
  njegovu noć", "Njegov' noćiš dobiješ ploče") and players steered
  duels away from a broke target ("On ima noćiče, ti nemaš").
- **Guard-post roll threshold possibly tightened.** Spoken as
  "Baci poviše četiri" ("roll above four", i.e. 5–6, 33%) rather
  than V0.10.2's `4+` ("4 or higher", 50%). Whether 4 actually paid
  at the table is not audible.
- **Pawn pass-through disputed.** V0.10.2 sets
  `pass_through_pawns: true`, but one exchange rejected moving
  through or onto another pawn: "Moš nema me doći. — Ne, ne moš."
- **"Gdje su ti na vratima, imaš jedan noćić"** — ambiguous between
  a house-ruled coin at your gate and the succession map's guard
  posts sitting three steps from each gate. No gate income exists
  in the JSON; the tape does not settle which was meant.
- **Level-2 rules withheld during teaching.** Deliberate choice by
  the teacher: "Nismo mu još objasnili ništa drugog nivora pa da mu
  nekomplikiramo."
- **Suspected dice manipulation.** Re-rolled after call-outs: "Dome
  vara za tebi", "Ali nema više varanja", "Are you cheating?"

## Family-session conditions

The session is the protocol's mixed family group, not the strategy
group. Long off-game digressions are on tape (a San Francisco
caramel candy tasting, pop songs, "Like i subscribe"). Two yelling
moments happened: the level-transition dispute and one player's
complaint about repeated attacks. These conditions set the floor
for what the record can show, and they match the protocol's
youngest-group setting.

## Observed problems (with quotes)

- **Zero-Prestige lockout, again, and this time to a child.** Luka
  ends with no tokens: "Luka nema ropčića" (twice) and "A ja nema
  ropčića." He cannot pay the fee and cannot contest, and he says
  so: "Kad ću ja dobiti šansu? Kaj je moj red?" Another player
  offered themselves as a duel target so he could farm a coin
  ("Bože ako dobiješ mene dobiješ ropčić i kad to onda ponovno").
  Income attribution confused others too: "Ja ne znam, gopi su i
  noćići ili samo ja dobija noćići."
- **Endgame pile-up and forced coalition.** After the beaten
  claimant used lorica to stay on the Peristyle ("Ali iskoristio
  haloriku i ostaje", followed by re-claim confusion: "Čo ga ti si
  klaimat'o? A ti ona klaima, oš klaima?"), everyone crowded onto
  the claim site: "I sad smo se svim nabili na jednom mjesto šta
  nije baš neki džir." Paying to fight felt forced: "I ja ću sad
  platiti jedan noćiš, jer nema ni izbora." Open kingmaking talk:
  "Daj moramo Filipa nekako", "A bolje je proti doma?"
- **Level-transition dispute.** Whether one more round is played
  after the first arrival at the Peristyle caused the loudest
  argument of the session: "Ide drugi level. — Nije. — A, ne, još
  jedan kruglje, sad mi odigravamo. — O, puti, prekini! — Ne deri
  se." The rule is right; "The Road to the Throne" on the player
  mat skips the extra round and jumps straight from claiming the
  Peristyle to searching faction cards.
- **Ordinary-duel displacement dispute.** One player sent an
  ordinary duel loser back to their gate, sparking an argument
  ("Zašto on ide na vrat? … Stani, ne znaš pravila") before another
  clarified that only a beaten claimant returns to their gate.
- **Pilum questioned as redundant.** Mid-palace, a heavily garbled
  line questions the pilum's purpose or suggests letting it stack
  with the gladius: "Pa ja mislim da je pivom treba radit vlade.
  Nema smisla baš pulno. Ili da se stakla zladi u sučinu."
- **Teach load for a new young player.** Roughly half the tape is
  teaching, with level-2 material deliberately withheld to keep
  the explanation short. Attention broke into songs and candy
  more than once. No explanation timer ran, so the minutes are
  unknown.
- **Movement bookkeeping.** Steps were counted aloud all session
  ("1, 2, 3… 11"), pawn positions were disputed ("Ja sam bila
  vamo… Ja sam bila na bronze gate"), and passing/landing on
  another pawn was contested ("Moš nema me doći. — Ne, ne moš.").
- **Naming splits the table by age.** One player: "Glupi su ovi
  nazivi majke" — about gate and street names. Session 001 had
  called the same names educational.

## Born at the table

- Token donation between players, with team play in mind:
  "Moramo napraviti, da se može tokeni donirati… Kada budemo tim."
- A ranking of the factions, invented because the cards are
  mechanically identical: "Koj je najbolji? Armija."
- Voluntary coin-farming duel target when a child went broke
  ("Bože ako dobiješ mene dobiješ ropčić i kad to onda ponovno").

## What this session answers from protocol.md

- Q1 (two-dice movement understood in one round): yes for early
  stop; pass-through and landing on another pawn stayed disputed.
- Q4 (succession feels like a race with a dramatic finish): yes —
  cheering through the final contests ("Go go go go go go go",
  "Ajdeee") and a survival finish: "Prživija se, al over."
- Q5 (younger players choose duels on purpose): yes — targets were
  chosen aloud ("Ja teši ovog", "A bolje je proti doma?") after a
  taught refusal option for the mover ("Može odabrati se neće
  boriti sa mene").
- Q6 (two-round window understood without help): yes — the window
  and the single-claim rule were restated correctly at the table.
- Q7 (rule causing most questions): the Prestige economy — who
  receives coins, bank vs loser transfer, and zero-coin recovery —
  plus displacement on duel loss and pawn-passing.
- Q2, Q3 (treasure entry clarity; palace drag): not settled by
  this tape.

Positive-evidence test (state the goal, name a choice, want
another game): choices were named and the goal was stated, but by
the teacher, not by the new player alone; "want another game" is
not on tape. Partially met.

## Interpretation (analysis, not record)

1. **The D56 two-round window has its first live confirmation.**
   Session 001 chose three rounds with an objection; this table
   played two, understood it, and the game ended on a survival.
   The claim-window arm of the model-context plan now has human
   evidence at its chosen value. The cost seen here is the pile-on:
   the window plus the fee plus lorica keeping a beaten claimant on
   the Peristyle made everyone crowd onto and pay into the same
   fight. The harness should sweep fee and window together, not one
   at a time.
2. **The Prestige drought hit a child — and two table misplays made
   it sharper.** The same endgame income failure that session 001
   hit struck the youngest player here, and the table's own patches
   (token donation, offering oneself as a duel pinata) are social
   workarounds for a rules gap. Two misplays compounded the printed
   drought: zero-sum loser-to-winner duel transfers (instead of
   bank-funded +1 to the winner) and possibly reading `4+` as
   `"poviše četiri"` (5–6). Even under exact V0.10.2 rules, though,
   a player who spends down to 0 Prestige has no guaranteed quick
   re-entry; any income change (gate pay, cheaper fee, free contest
   for a broke player, or easier guard posts) should be simulated
   before it is printed.
3. **The one-modifier duel rule did its job — and exposed the pilum
   as strictly dominated by the gladius.** Session 001's top
   clarification — mid-duel bonus recounting — never happened.
   Abilities were named as single plus-ones and applied without
   arithmetic disputes. But under `bonus_per_side: "best"`, gladius
   (+1 in any attack) completely subsumes pilum (+1 attacking the
   claimant) once a player holds both — which every full-set
   collector does by Level 2. A player spotted that live and asked
   for pilum to do something else or stack.
4. **The galea looked overpowered because the table played it
   off-rules — invited by the player mat.** In V0.10.2, galea only
   publicly reveals a Palace treasure card. The player mat prints
   `"Galea — action: reveal a card"` with no phase, deck, or
   public/private qualifier, so the table naturally held it for
   Level 2 and turned it into a private faction scout. This gives
   two clear design options: tighten the mat and card text so galea
   stays Palace-only and public, or intentionally adopt and sim-test
   a once-per-game faction-card reveal (since humans instinctively
   found saving galea for Level 2 exciting).
5. **Four table disputes trace directly to player-mat omissions.**
   Without touching core mechanics, the print kit can eliminate
   the four sharpest arguments heard on tape by stating on the mat:
   (a) the `+1 full round` grace round in "The Road to the Throne",
   (b) that only a beaten *claimant* returns to their gate (ordinary
   duels do not displace), (c) galea's exact phase/deck/visibility,
   and (d) `pass through pawns` on the turn summary line, plus
   emphasizing `"from the bank"` next to `+1 win any duel`.
6. **Where the tape cannot go.** No timing, no form, no per-player
   probe answers. The next family session should run the timer and
   the four understanding probes, and the recorder should sit closer
   to the table; the loop artifact lost a block of audio.
