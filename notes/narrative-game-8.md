# Narrative game 8 — displacement variant playtest

Run: `runs/narr8`, rules `rules_v03_displacement.json`, seed 4301. One change
on the base rules: any duel loser is displaced to the retreat node `[2,3]`.
Personas: P0 Custos (guards the Emperor door), P1 Velox (pure speed), P2
Ictus (duels before his own Emperor attempts), P3 Aquila (farms Glory, buys
seals, adapts). 50 act calls, no illegal actions.

## Outcome (from `runs/narr8/result.json`)

Winner: **P3 "Aquila"** by Emperor (`emperor_hits 2/2`), turn 50, Level 2
round 5. Comeback win: first challenger P0 (Custos) lost. Totals: 50 turns,
32 Level 1 / 18 Level 2, no timeouts. Emperor ledger: P3 2/2 attempts, P0
1/2, P1 and P2 never attacked. Seven duels produced seven displacements.
Aquila earned 3 Glory (two guard posts, one duel) and spent it all: the
peristyle seal plus two boosted Emperor swings.

## Findings

- **Custos reached the door this time and still could not guard it.** Unlike
  game 7, he claimed the chamber, hit the Emperor on turn 42, and stood in
  the doorway. Guarding bars nothing: pawns pass through each other and
  share nodes. His only weapon, the duel, throws losers to `[2,3]`, which is
  one step from the chamber. On turn 39 he declined to kick a two-seal
  Aquila because the kick would have delivered him to the doorstep.
- **Displacement delayed no Emperor attempt all game.** Of seven
  displacements, four fell in the Level 1 grace round (positions reset at
  transition, so they cost nothing), one was a no-op (`[2,3]` to `[2,3]`),
  and two moved the victim closer to the chamber: Custos `[2,4]` to `[2,3]`
  on turn 44, Ictus `[1,2]` to `[2,3]` on turn 49. Both victims attacked on
  schedule afterward. A kicked player never walked back because the drop
  point sits at the door.
- **Players stopped fearing duels and started farming them.** Losing now
  teleports you to the best node on the board, so provocations became
  win-win. Aquila baited Custos on turn 44 knowing a win paid Glory and a
  loss paid distance. Ictus dueled on turn 49 wanting either outcome, lost,
  and landed one step from the Emperor he was armed to attack.
- **The guard tactic backfired by geometry, not by dice.** Ties go to the
  attacker, which favored Custos whenever he swung, and Level 2 equipment
  was equal everywhere. The backfire was the drop point: when Aquila beat
  Custos (turn 44) and Velox beat Aquila (turn 48), each loser left the
  chamber, stepped back in one edge, and swung anyway. Velox's "interference"
  won him Glory and changed no one's tempo.
- **Grace rounds became a duel farm.** Turns 27 to 32 held four duels.
  Displacement was free there, and Glory carries across the transition, so
  every seat below the Glory cap had a reason to swing. Velox, kicked three
  times, lost nothing: all three drops fell in that window, and he later
  used the rule offensively by beating Aquila in the chamber on turn 48.
- **The race was more interactive than earlier reports, but not more
  contested.** Previous games describe a solitaire seal-and-swing race. Here
  players fought at the door, baited kicks, and three pawns stacked on
  `[2,3]` by the end. Yet the winner was still decided by the Glory economy:
  Aquila's two Level 1 guard-post successes bought his seal and both
  Emperor swings. The crowd at the door watched him win.
- **Design signal.** Displacement fails because the drop point is adjacent
  to the Emperor chamber. A retreat far from the victim's goal, or a tempo
  cost such as a skipped turn, is needed before a kick can stall anyone.
  Open question: let the loser retreat one step of their choice instead of
  teleporting, so the attacker controls direction but not distance?
