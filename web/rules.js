/* The full rulebook for the web board, matching the repository's
 * measured ruleset (rules_v06_realboard_p3.json) and the print pack
 * rulebook word for word where they overlap. Rendered into an
 * overlay by app.js. */
(function (global) {
  "use strict";

  global.DIOCLET_RULES = `
<h2>The game in one minute</h2>
<p>Four players enter a walled Roman city through four gates. First,
gear up in the city blocks. Then the gate opens and everyone races
through the palace: two seals, then two strikes on the Emperor. The
first to land <b>two hits</b> on the Emperor wins.</p>

<h2>What you need</h2>
<ul>
  <li>Two ordinary six-sided dice for <b>movement</b> (add them
  together).</li>
  <li>One six-sided die for <b>every fight and trial</b>: guard
  posts, duels, seals, Emperor strikes.</li>
  <li>The board: 107 street circles. The red blocks are buildings;
  nobody walks there.</li>
</ul>

<h2>Setup</h2>
<ul>
  <li>Each player takes a gate: north, east, south, or west. All
  four are equal, so pick freely.</li>
  <li>Shuffle the six treasure cards face down, one on each blue
  entry space. Nobody knows which block holds which treasure.</li>
  <li>Everyone starts with no treasure and no Glory. Choose a
  starting player at random; the start moves one seat clockwise
  <b>every round</b>.</li>
</ul>

<h2>Your turn</h2>
<ol>
  <li><b>Roll both movement dice.</b> The sum is your <i>maximum</i>
  steps, not an exact count.</li>
  <li><b>Move</b> along the street circles, up to your roll. You may
  stop early. You may pass through other pawns; walking past someone
  never starts a fight.</li>
  <li><b>Do one thing</b> at the circle you reach (or simply end
  your move). One action per turn, never two.</li>
</ol>
<p class="note">Guard posts and duels always need a move of at least
one space first. You cannot use either of them twice from the same
spot without moving away and coming back.</p>

<h2>The city: four actions</h2>
<table>
  <tr><th>Action</th><th>Rule</th></tr>
  <tr><td><b>Take a treasure</b><br><span class="where">blue entry</span></td>
      <td>End your move on a block's entry circle and take that
      block's treasure. When a card is first taken it is revealed to
      everyone. Every treasure can be taken by every player once.
      Treasure is never stolen and never lost.</td></tr>
  <tr><td><b>Stand guard</b><br><span class="where">green star</span></td>
      <td>Move onto a guard post and roll one die: <b>4, 5 or 6
      earns 1 Glory</b>. This is the board's reliable way to earn
      Glory.</td></tr>
  <tr><td><b>Duel a rival</b><br><span class="where">within 2 spaces</span></td>
      <td>End your move within two street spaces of another pawn to
      challenge them. Each of you rolls one die and adds a gear
      bonus. Higher total wins; <b>ties go to the attacker</b>. The
      winner takes 1 Glory. Nobody loses anything else.</td></tr>
  <tr><td><b>Open the gate</b><br><span class="where">gold circle</span></td>
      <td>The first player who owns all six treasures and reaches
      the central checkpoint takes 1 Glory and opens the gate to the
      palace. Only the first claim counts.</td></tr>
</table>

<h3>Gear bonus</h3>
<table>
  <tr><th>Treasures owned</th><th>0 to 2</th><th>3 to 5</th><th>all 6</th></tr>
  <tr><td>Added to duels, barracks, Emperor</td><td>+0</td><td>+1</td><td>+2</td></tr>
</table>

<h3>Glory</h3>
<p>You may hold at most <b>2</b>. Anything earned beyond that is
lost, so spend it or waste it. You earn it three ways (guard post,
duel win, first through the gate) and it buys exactly two things:
the guaranteed Peristyle seal, and a powered Emperor strike.</p>

<h2>The gate</h2>
<p>When the checkpoint is claimed, finish that round, then play
<b>one more full round</b> in the city, a last chance for treasure,
Glory, or a grudge match. Then:</p>
<ul>
  <li>Every player still missing treasures receives them
  <b>for free</b>. Nobody is left behind.</li>
  <li>All pawns return to their gates; Glory is kept; the palace
  begins.</li>
  <li>If nobody claims the checkpoint by the end of round 24, the
  gate opens anyway with the same free gear.</li>
</ul>

<h2>The palace</h2>
<p>The blocks change roles. You need <b>any two different seals</b>
before the Emperor will face you. You cannot repeat a seal you
already own. Duels work exactly as in the city.</p>
<table>
  <tr><th>Seal</th><th>Where</th><th>How to earn it</th></tr>
  <tr><td><b>Cellars</b></td><td>northwest, on entry A (c)</td>
      <td>Roll one die: <b>3 or more</b>.</td></tr>
  <tr><td><b>Barracks</b></td><td>southeast, on entry F (b)</td>
      <td>You roll die + gear bonus; the guard rolls die +1.
      <b>Beat the guard strictly.</b></td></tr>
  <tr><td><b>Peristyle</b></td><td>center, on the checkpoint (p)</td>
      <td>Roll one die: <b>5 or 6</b>. Or simply <b>pay 1 Glory</b>
      for it, no roll. The safe buy.</td></tr>
</table>

<h2>The Emperor</h2>
<ol>
  <li>Stand in his chamber (red E, the south gate) and strike: you
  roll die + gear bonus, he rolls die +2. <b>Score strictly higher
  to hit.</b></li>
  <li>You may <b>declare a powered strike before rolling: pay 1
  Glory for +2</b> to your roll, paid whether you hit or miss. A
  powered strike lands about 7 times in 10; a free one about 45 in
  100.</li>
  <li><b>Hit:</b> mark it, stay in the chamber, strike again next
  turn. <b>Miss:</b> step back one space to the retreat hall.
  Nothing else is lost.</li>
  <li><b>The first player to two hits wins immediately.</b> If
  nobody succeeds by the end of round 24 of the palace phase, the
  game is a draw.</li>
</ol>

<h2>What everyone may see</h2>
<p>Everything is public: positions, treasures, Glory, seals, hits,
and all revealed cards. The only secrets are the face-down treasures
and the next roll.</p>

<h2>Two final notes</h2>
<p>Every gate is equally good, and comebacks are the norm, not the
exception: in measured play the player who was behind at the gate
wins most games. If you trail, fight for Glory; it is the currency
that decides the Emperor.</p>
<p class="provenance">These rules are the measured V0.6 real-board
ruleset: every number here was tested across tens of thousands of
simulated games before it was written down.</p>`;
})(typeof window !== "undefined" ? window : globalThis);
