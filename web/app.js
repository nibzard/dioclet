/* Diocletian's Palace: table UI over web/engine.js and web/bots.js. */
(function () {
  "use strict";

  const B = window.DIOCLET_BOARD;
  const E = window.DIOCLET_ENGINE;
  const BOTS = window.DIOCLET_BOTS;
  const CELL = 44, PAD = 36;
  const COLORS = { P0: "#5a3d6b", P1: "#b0532f", P2: "#5f7a4a", P3: "#3f6f9e" };
  const SEATNAMES = { P0: "North", P1: "East", P2: "South", P3: "West" };
  const KINDS = [["human", "Human (this device)"], ["balanced", "Bot: balanced"],
                 ["greedy", "Bot: collector"], ["aggressive", "Bot: fighter"],
                 ["random", "Bot: wanderer"]];

  const svg = document.getElementById("board");
  const NS = "http://www.w3.org/2000/svg";
  let g = null, seed = 2026, botTimer = null, animCells = [];

  const cx = x => PAD + x * CELL + CELL / 2;
  const cy = y => PAD + y * CELL + CELL / 2;
  const K = (x, y) => x + "," + y;
  const at = k => k.split(",").map(Number);

  function el(name, attrs, parent, text) {
    const e = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
    if (text !== undefined) e.textContent = text;
    (parent || svg).appendChild(e);
    return e;
  }

  /* ---------------- board rendering ---------------- */

  function buildBoard() {
    const w = PAD * 2 + B.width * CELL, h = PAD * 2 + B.height * CELL;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    el("rect", { width: w, height: h, fill: "#f6efe2", rx: 14 });
    el("rect", { x: 8, y: 8, width: w - 16, height: h - 16, rx: 12,
                 fill: "none", stroke: "#9c8a64", "stroke-width": 4 });
    for (const [x, y] of B.blocked) {
      el("rect", { x: PAD + x * CELL + 2, y: PAD + y * CELL + 2,
                   width: CELL - 4, height: CELL - 4, rx: 5,
                   fill: "#c96b4f", stroke: "#9c4a33", "stroke-width": 1.4 });
    }
    for (let y = 0; y < B.height; y++) {
      for (let x = 0; x < B.width; x++) {
        if (B.blocked.some(c => c[0] === x && c[1] === y)) continue;
        const k = K(x, y);
        el("circle", { cx: cx(x), cy: cy(y), r: 13, fill: "#fffdf6",
                       stroke: "#b7a77f", "stroke-width": 2, "data-k": k,
                       class: "cell" });
      }
    }
    const chip = (k, fill, text) => {
      const [x, y] = at(k);
      el("circle", { cx: cx(x), cy: cy(y), r: 16.5, fill,
                     stroke: "#3a2d20", "stroke-width": 2.5 });
      el("text", { x: cx(x), y: cy(y) + 5.5, "text-anchor": "middle",
                   "font-family": "Georgia, serif", "font-size": 16,
                   "font-weight": "bold", fill: "#fffdf6" }, svg, text);
    };
    for (const [p, c] of Object.entries(B.gates)) {
      chip(K(...c), "#5a3d6b", { P0: "N", P1: "E", P2: "S", P3: "W" }[p]);
    }
    for (const [n, c] of Object.entries(B.districts)) chip(K(...c), "#3f6f9e", n);
    chip(K(...B.checkpoint), "#c9972b", "X");
    for (const c of B.gloryPosts) chip(K(...c), "#5f7a4a", "*");
    chip(K(...B.level2.emperor), "#a03d2e", "E");
    chip(K(...B.level2.retreat), "#4a6b7a", "r");
    for (const [label, site] of [["c", "cellars"], ["b", "guard_barracks"],
                                 ["p", "peristyle"]]) {
      const [x, y] = B.level2[site];
      el("circle", { cx: cx(x) + 14, cy: cy(y) - 15, r: 8, fill: "#fffdf6",
                     stroke: "#3a2d20", "stroke-width": 1.4 });
      el("text", { x: cx(x) + 14, y: cy(y) - 11.5, "text-anchor": "middle",
                   "font-family": "Verdana, sans-serif", "font-size": 10,
                   fill: "#3a2d20" }, svg, label);
    }
    svg.addEventListener("click", onBoardClick);
  }

  function pawnFor(id) { return document.getElementById("pawn-" + id); }

  function placePawns() {
    for (const p of g.players) {
      if (pawnFor(p.id)) continue;
      const grp = el("g", { id: "pawn-" + p.id, class: "pawn" });
      el("circle", { r: 9.5, fill: COLORS[p.id], stroke: "#fffdf6",
                     "stroke-width": 2.2 }, grp);
      el("text", { y: 3.6, "text-anchor": "middle", fill: "#fffdf6",
                   "font-family": "Verdana, sans-serif", "font-size": 8.5,
                   "font-weight": "bold" }, grp, SEATNAMES[p.id][0]);
      svg.appendChild(grp);
      setPawn(p.id, p.pos);
    }
  }

  function setPawn(id, k) {
    const [x, y] = at(k);
    pawnFor(id).setAttribute("transform",
      `translate(${cx(x)},${cy(y)})`);
  }

  async function animatePawn(id, fromK, toK) {
    const p = g.players.find(q => q.id === id);
    const steps = E.path(fromK, toK);
    if (steps.length < 2) { setPawn(id, toK); return; }
    for (const step of steps.slice(1)) {
      setPawn(id, step);
      await new Promise(r => setTimeout(r, 110));
    }
  }

  function showRevealed() {
    for (const [k, item] of Object.entries(g.revealed)) {
      if (document.getElementById("rv-" + k)) continue;
      const [x, y] = at(k);
      el("text", { id: "rv-" + k, x: cx(x), y: cy(y) + 27,
                   "text-anchor": "middle", "font-family": "Verdana, sans-serif",
                   "font-size": 8.5, fill: "#7a5c2e", class: "revealchip" },
         svg, item.replace("lorica_segmentata", "armor").slice(0, 9));
    }
  }

  /* ---------------- side panel ---------------- */

  function renderPlayers() {
    const box = document.getElementById("players");
    box.innerHTML = "";
    for (const p of g.players) {
      const isActive = !g.winner && !g.draw &&
                       E.active(g).id === p.id;
      const d = document.createElement("div");
      d.className = "pcard" + (isActive ? " active" : "");
      const glory = [0, 1].map(i =>
        `<span class="gtoken ${i < p.glory ? "" : "off"}"></span>`).join("");
      const seals = ["cellars", "guard_barracks", "peristyle"].map(s =>
        `<span class="sealtag ${p.seals.includes(s) ? "got" : ""}">` +
        { cellars: "C", guard_barracks: "B", peristyle: "P" }[s] + `</span>`).join("");
      d.innerHTML =
        `<div class="pname"><span><span class="pawnchip"
           style="background:${COLORS[p.id]}"></span>${p.name}</span>
         <span class="muted small">${p.kind === "human" ? "human" : p.kind}</span></div>
         <div class="pstats">${glory} gear ${p.equipment.length}/6
         ${g.phase === 2 ? "· seals " + seals + " · <span class='hittag'>" +
           "✦".repeat(p.hits) + "</span>" : ""}</div>`;
      box.appendChild(d);
    }
  }

  function renderDice(extra) {
    const box = document.getElementById("dice");
    box.innerHTML = "";
    if (!g.currentRoll) return;
    for (const d of g.currentRoll.dice) {
      const die = document.createElement("div");
      die.className = "die"; die.textContent = d;
      box.appendChild(die);
    }
    if (extra) {
      for (const d of extra) {
        const die = document.createElement("div");
        die.className = "die event"; die.textContent = d;
        box.appendChild(die);
      }
    }
    const tot = document.createElement("div");
    tot.id = "dicetotal";
    tot.textContent = "= " + g.currentRoll.total +
      (extra && extra.length ? " moves" : " max steps");
    box.appendChild(tot);
  }

  function renderLog() {
    const box = document.getElementById("log");
    box.innerHTML = "";
    const lines = g.log.slice(-60);
    for (const line of lines) {
      const d = document.createElement("div");
      d.textContent = line;
      if (/HIT|wins|defeats/.test(line)) d.className = "evt";
      if (/Glory/.test(line)) d.className = "glory";
      box.appendChild(d);
    }
    box.scrollTop = box.scrollHeight;
  }

  function renderTurnline() {
    const line = document.getElementById("turnline");
    if (g.winner) {
      const p = E.player(g, g.winner);
      line.textContent = `${p.name} defeated the Emperor. Game over.`;
      return;
    }
    if (g.draw) { line.textContent = "The palace gates closed: a draw."; return; }
    const p = E.active(g);
    const phase = g.phase === 1 ? "the city" : "the palace";
    line.textContent = `Round ${g.round} in ${phase} — ${p.name}` +
      (p.kind === "human" ? " (your turn)" : " is thinking…");
  }

  /* ---------------- interaction ---------------- */

  let actions = [], byDest = new Map();

  function refreshActions() {
    clearHighlights();
    document.getElementById("actionbox").innerHTML = "";
    if (g.winner || g.draw) return;
    actions = E.legalActions(g);
    byDest = new Map();
    for (const a of actions) {
      if (!byDest.has(a.dest)) byDest.set(a.dest, []);
      byDest.get(a.dest).push(a);
    }
    for (const k of byDest.keys()) {
      const c = svg.querySelector(`[data-k="${k}"]`);
      if (c) c.classList.add("reachable");
    }
  }

  function clearHighlights() {
    for (const c of svg.querySelectorAll(".reachable")) {
      c.classList.remove("reachable");
    }
  }

  function onBoardClick(ev) {
    const c = ev.target.closest(".cell");
    if (!c || g.winner || g.draw) return;
    const p = E.active(g);
    if (p.kind !== "human") return;
    const k = c.getAttribute("data-k");
    const list = byDest.get(k);
    if (!list) return;
    if (list.length === 1) { humanAct(list[0]); return; }
    const box = document.getElementById("actionbox");
    box.innerHTML = `<div class="hint">Choose what to do at ${k}:</div>`;
    for (const a of list) {
      const b = document.createElement("button");
      b.className = "choice";
      b.innerHTML = describe(a);
      b.onclick = () => humanAct(a);
      box.appendChild(b);
    }
  }

  function describe(a) {
    const siteNames = { cellars: "Cellars", guard_barracks: "Barracks",
                        peristyle: "Peristyle" };
    switch (a.kind) {
      case "move": return "Just <b>walk</b> here";
      case "explore": return `<b>Take the treasure</b> (${a.item
        .replace("lorica_segmentata", "armor")})`;
      case "guard_post": return "<b>Stand guard</b> — roll for Glory";
      case "duel": {
        const q = E.player(g, a.target);
        return `<b>Duel ${q.name}</b>`;
      }
      case "claim_checkpoint": return "<b>Open the gate</b> — first through";
      case "attempt_seal": return a.spend
        ? `<b>Buy the seal</b> at the ${siteNames[a.site]} (1 Glory)`
        : `<b>Roll for the seal</b> at the ${siteNames[a.site]}`;
      case "attack_emperor": return a.spend
        ? "<b>Powered strike</b> — pay 1 Glory for +2"
        : "<b>Strike the Emperor</b>";
    }
    return a.kind;
  }

  async function humanAct(a) {
    document.getElementById("actionbox").innerHTML = "";
    await perform(a);
  }

  async function perform(a) {
    const p = E.active(g);
    const from = p.pos;
    clearHighlights();
    const rec = E.applyAction(g, a);
    if (a.kind !== "attack_emperor" || rec.dice.length === 0) {
      await animatePawn(p.id, from, a.dest);
    } else { setPawn(p.id, p.pos); }
    if (a.kind === "attack_emperor" && p.pos !== a.dest) setPawn(p.id, p.pos);
    renderDice(rec.dice);
    showRevealed();
    renderPlayers(); renderLog(); renderTurnline();
    if (g.winner || g.draw) { showGameOver(); return; }
    refreshActions();
    renderDice();
    scheduleBot();
  }

  function scheduleBot() {
    const p = E.active(g);
    if (p.kind === "human" || g.winner || g.draw) return;
    clearTimeout(botTimer);
    botTimer = setTimeout(async () => {
      const acts = E.legalActions(g);
      const rng = () => g.rng();
      const a = BOTS.choose(p.kind === "human" ? "balanced" : p.kind,
                            { ...g, activePlayer: p }, acts, rng);
      await perform(a);
    }, 650);
  }

  function showGameOver() {
    const over = document.getElementById("gameover");
    document.getElementById("overline").textContent = g.winner
      ? E.player(g, g.winner).name + " rules the palace!"
      : "A draw in the palace.";
    document.getElementById("oversub").textContent =
      `Seed ${g.seed} · ${g.round} rounds · ` +
      g.players.map(p => `${p.name}: ${p.equipment.length} gear` +
        (g.phase === 2 ? `, ${p.seals.length} seals, ${p.hits} hits` : ""))
        .join(" · ");
    over.classList.remove("hidden");
  }

  /* ---------------- setup ---------------- */

  function buildSetup() {
    const seats = document.getElementById("seats");
    seats.innerHTML = "";
    for (const [pid, label] of Object.entries(SEATNAMES)) {
      const d = document.createElement("div");
      d.className = "seat";
      d.innerHTML =
        `<label>${label} gate (${pid})</label>
         <input id="name-${pid}" value="Player ${label}" maxlength="16">
         <select id="kind-${pid}">` +
        KINDS.map(([v, t]) =>
          `<option value="${v}" ${v === "human" ? "" : ""}>${t}</option>`)
          .join("") + `</select>`;
      seats.appendChild(d);
    }
    document.getElementById("kind-P1").value = "balanced";
    document.getElementById("kind-P2").value = "balanced";
    document.getElementById("kind-P3").value = "greedy";
    document.getElementById("startbtn").onclick = () => {
      seed = parseInt(document.getElementById("seed").value, 10) || 2026;
      startGame(false);
    };
    document.getElementById("watchbtn").onclick = () => {
      seed = Math.floor(Math.random() * 1e9);
      startGame(true);
    };
    document.getElementById("againbtn").onclick = () => {
      document.getElementById("gameover").classList.add("hidden");
      startGame(false, true);
    };
    document.getElementById("setupbtn").onclick = () => {
      document.getElementById("gameover").classList.add("hidden");
      document.getElementById("setup").classList.remove("hidden");
    };
  }

  function startGame(watch, reuseSeats) {
    clearTimeout(botTimer);
    document.getElementById("setup").classList.add("hidden");
    for (const rv of [...svg.querySelectorAll(".revealchip")]) rv.remove();
    const seats = ["P0", "P1", "P2", "P3"].map(pid => ({
      id: pid,
      kind: watch ? "balanced" :
        (reuseSeats ? g.players.find(p => p.id === pid).kind
          : document.getElementById("kind-" + pid).value),
      name: watch ? pid :
        (reuseSeats ? g.players.find(p => p.id === pid).name
          : (document.getElementById("name-" + pid).value || pid)),
    }));
    if (watch) seats[1].kind = "greedy";
    g = E.newGame(seed, seats);
    g.log.push("The city gates open. Six treasures wait in the blocks.");
    placePawns();
    renderPlayers(); renderDice(); renderLog(); renderTurnline();
    refreshActions();
    scheduleBot();
  }

  buildBoard();
  buildSetup();
  document.getElementById("setup").classList.remove("hidden");
})();
