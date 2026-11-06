# Narrative game 7 — interference hunger playtest

Run: `runs/narr7`, rules `rules_baseline.json`, seed 4202, engine with the
corrected failed-Emperor-attack retreat to `[2,3]`. Personas: P0 Custos
(guards the Emperor door), P1 Velox (pure speed), P2 Murmur (duels leaders),
P3 Aquila (farms Glory, buys everything). 55 act calls, no illegal actions.

## Outcome (from `runs/narr7/result.json`)

Winner: **P2 "Murmur"** by Emperor (`emperor_hits 2/2`), turn 55, Level 2
round 5. Comeback win: first challenger P1 (Velox) lost. Totals: 55 turns,
36 Level 1 / 19 Level 2, no phase timeouts. Emperor ledger: P2 2/2, P3 0/3,
P0 and P1 never attacked. P2 went 4/4 in duels and spent 3 Glory
(1 peristyle seal, 2 Emperor swings) — the duel-hunger persona funded its
own win, not anyone's delay.

## Findings

- **No, players could not interfere with a Level 2 leader.** A duel takes
  nothing from the loser (no position, seals, hits, or turns) and only pays
  Glory to the winner, so attacking a leader risks handing them Emperor
  fuel. Every persona independently converged on refusing to duel P2 once
  he had one hit; the final three turns were watched helplessly.
- **Murmur won four duels and delayed nothing.** He beat P1 twice in Level 1;
  P1 claimed the checkpoint one turn later anyway. He beat P3 (turn 47) while
  P3 was en route; P3 attacked the Emperor on his very next turn. Duels were
  pure Glory farming for the attacker — Murmur's "harassment" was actually
  his win condition (3 Glory earned, 3 spent).
- **Custos's door-guarding accomplished nothing, by rule.** He never even
  reached the door in time (still on his second seal, turn 52, when P2 hit),
  but the deeper issue is mechanical: a duel at the door resolves on the
  guard's turn, costs the intruder nothing, and blocks no entry. Camping the
  door can only farm Glory for the guard or feed the intruder. The persona
  had no legal move that bars anything.
- **Corrected miss-retreat works but barely punishes.** All three of P3's
  misses bounced him to `[2,3]` as designed — but `[2,3]` is one step from
  the chamber, and any roll of 1+ allows a return-and-attack, so a miss
  costs almost no tempo. It also creates no blocking point: the chamber is
  a shared site with pass-through, so nobody can occupy or contest it.
- **The chamber still invites camping, now by winners.** P2's first hit
  kept him in the chamber with a free stationary re-attack. Nothing any
  opponent did between his hits (turns 52-55) could touch him.
- **Grace rounds are dead air for capped players.** Turns 26-36: Murmur and
  Aquila sat at Glory cap 2 with all remaining equipment auto-granted at
  transition — no purchase, no block, no useful move. Both noted the
  frustration explicitly (it is data: the catch-up rule creates a 2-3 round
  nobody-can-act window).
- **Glory economy decided the game, not interaction.** All four players
  bought their first seal at the peristyle with 1 Glory; Level 1 guard-post
  income became Level 2 sealed tempo. Aquila's farm-and-buy plan was sound
  but dice-neutral: he reached the chamber first and went 0-for-3.
- **The finish was tense for one turn only.** P2 at one hit on turn 51 made
  turns 52-55 a known countdown; P3's last-gasp attack (turn 54) missed and
  ended it. No player action could change the outcome — only P2's die could.

Open question for the designer: if interference is a design goal, duels
need a cost to the loser (Glory theft, a lost turn, or a displacement), or
the Emperor door needs a contestable hold action.
