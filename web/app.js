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
  let g = null, seed = 2026, botTimer = null;

  const cx = x => PAD + x * CELL + CELL / 2;
  const cy = y => PAD + y * CELL + CELL / 2;
  const K = (x, y) => x + "," + y;
  const at = k => k.split(",").map(Number);
  const escapeHTML = value => String(value).replace(/[&<>"']/g, ch =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
  const reducedMotion = () => window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const previousFocus = new Map();
  function syncDialogs() {
    const open = [...document.querySelectorAll(".overlay:not(.hidden)")];
    const top = open.find(d => d.id === "rules") || open.at(-1);
    for (const node of document.querySelectorAll("body > header, .table-heading, main, .site-footer, .overlay")) {
      node.inert = Boolean(top && node !== top);
    }
    document.body.style.overflow = top ? "hidden" : "";
  }
  function showOverlay(id) {
    const node = document.getElementById(id);
    previousFocus.set(id, document.activeElement);
    node.classList.remove("hidden");
    syncDialogs();
    node.focus();
  }
  function hideOverlay(id) {
    document.getElementById(id).classList.add("hidden");
    syncDialogs();
    const previous = previousFocus.get(id);
    if (previous && previous.isConnected && !previous.closest(".hidden")) previous.focus();
  }

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
    el("rect", { width: w, height: h, fill: "#efecdf", rx: 5 });
    el("rect", { x: 8, y: 8, width: w - 16, height: h - 16, rx: 3,
                 fill: "none", stroke: "#bdbea6", "stroke-width": 1.5 });
    el("rect", { x: 14, y: 14, width: w - 28, height: h - 28, rx: 2,
                 fill: "none", stroke: "#cfd0b9", "stroke-width": .8 });
    // Find each connected city block from the authoritative board data.
    const remaining = new Set(B.blocked.map(c => K(...c)));
    const blocks = [];
    while (remaining.size) {
      const first = remaining.values().next().value;
      remaining.delete(first);
      const group = [at(first)];
      for (let i = 0; i < group.length; i++) {
        const [x, y] = group[i];
        for (const [nx, ny] of [[x-1,y], [x+1,y], [x,y-1], [x,y+1]]) {
          if (remaining.delete(K(nx, ny))) group.push([nx, ny]);
        }
      }
      blocks.push(group);
    }
    blocks.sort((a, b) => Math.min(...a.map(c => c[1])) - Math.min(...b.map(c => c[1])) ||
      Math.min(...a.map(c => c[0])) - Math.min(...b.map(c => c[0])));
    const districts = Object.entries(B.districts).sort((a, b) => a[1][1] - b[1][1] || a[1][0] - b[1][0]);
    blocks.forEach((cells, i) => {
      const left = PAD + Math.min(...cells.map(c => c[0])) * CELL + 3;
      const top = PAD + Math.min(...cells.map(c => c[1])) * CELL + 3;
      const width = (Math.max(...cells.map(c => c[0])) - Math.min(...cells.map(c => c[0])) + 1) * CELL - 6;
      const height = (Math.max(...cells.map(c => c[1])) - Math.min(...cells.map(c => c[1])) + 1) * CELL - 6;
      const district = districts[i];
      const group = el("g", { "pointer-events": "none", "aria-hidden": "true" });
      el("rect", { x: left, y: top, width, height, rx: 4, fill: "#d9d5c2", stroke: "#b7b89d", "stroke-width": 1.3 }, group);
      // Inset masonry gives the blocks an architectural plan treatment.
      for (let x = left + 12; x < left + width - 8; x += CELL) {
        el("path", { d: `M${x} ${top + 7}v${height - 14}`, stroke: "#c7c7af", "stroke-width": 1 }, group);
      }
      for (let y = top + 12; y < top + height - 8; y += CELL) {
        el("path", { d: `M${left + 7} ${y}h${width - 14}`, stroke: "#c7c7af", "stroke-width": 1 }, group);
      }
      el("rect", { x: left + 20, y: top + 20, width: width - 40, height: height - 40, rx: 2,
        fill: "#e9e6d7", stroke: "#bbbea3", "stroke-width": 1 }, group);
      el("rect", { x: left + 26, y: top + 26, width: width - 52, height: height - 52, rx: 1,
        fill: "none", stroke: "#d0d1ba", "stroke-width": .8 }, group);
      if (district) {
        const midX = left + width / 2, midY = top + height / 2;
        el("text", { x: midX, y: midY - 43, "text-anchor": "middle", fill: "#7f866e",
          "font-family": "Verdana, sans-serif", "font-size": 8, "letter-spacing": 2 }, group, "DISTRICT " + district[0]);
        el("rect", { x: midX - 20, y: midY - 30, width: 40, height: 48, rx: 19,
          fill: "#f3f0e4", stroke: "#a7af93", "stroke-width": 1 }, group);
        el("text", { id: "treasure-" + K(...district[1]), x: midX, y: midY + 3,
          "text-anchor": "middle", fill: "#8c977b", "font-family": "Georgia, serif", "font-size": 29 }, group, "?");
        el("text", { id: "district-" + K(...district[1]), x: midX, y: midY + 41,
          "text-anchor": "middle", fill: "#7d866d", "font-family": "Verdana, sans-serif",
          "font-size": 9 }, group, "Hidden treasure");
      }
    });
    for (let y = 0; y < B.height; y++) {
      for (let x = 0; x < B.width; x++) {
        if (B.blocked.some(c => c[0] === x && c[1] === y)) continue;
        const k = K(x, y);
        el("circle", { cx: cx(x), cy: cy(y), r: 13, fill: "#fbf9ee",
                       stroke: "#c0c4ab", "stroke-width": 1.5, "data-k": k,
                       class: "cell" });
      }
    }
    const TITLES = {
      gate: "Gate and start position",
      entry: "Treasure entry: stop here to take the card",
      checkpoint: "Checkpoint: first with all six treasures opens the" +
                  " gate; also the Peristyle seal in the palace",
      post: "Guard post: roll 4 or more for 1 Glory",
      emperor: "The Emperor's chamber: two hits win the game",
      retreat: "Retreat hall: step back here on a missed strike",
    };
    // Decorations never block clicks or hover: the street circle under
    // a chip owns the pointer and carries the tooltip.
    const chip = (k, fill, text) => {
      const [x, y] = at(k);
      el("circle", { cx: cx(x), cy: cy(y), r: 16.5, fill,
                     stroke: "#3a2d20", "stroke-width": 2.5,
                     "pointer-events": "none" });
      el("text", { x: cx(x), y: cy(y) + 5.5, "text-anchor": "middle",
                   "font-family": "Georgia, serif", "font-size": 16,
                   "font-weight": "bold", fill: "#fffdf6",
                   "pointer-events": "none" }, svg, text);
    };
    const tip = (k, text) => {
      const c = svg.querySelector(`[data-k="${k}"]`);
      if (!c) return;
      const t = document.createElementNS(NS, "title");
      t.textContent = text;
      c.appendChild(t);
      c.setAttribute("aria-label", text);
    };
    for (const [p, c] of Object.entries(B.gates)) {
      chip(K(...c), "#5a3d6b", { P0: "N", P1: "E", P2: "S", P3: "W" }[p]);
      tip(K(...c), TITLES.gate + " (" + p + ")");
    }
    for (const [n, c] of Object.entries(B.districts)) {
      chip(K(...c), "#3f6f9e", n);
      tip(K(...c), TITLES.entry + " (" + n + ")");
    }
    chip(K(...B.checkpoint), "#c9972b", "X");
    tip(K(...B.checkpoint), TITLES.checkpoint);
    for (const c of B.gloryPosts) {
      chip(K(...c), "#5f7a4a", "*");
      tip(K(...c), TITLES.post);
    }
    chip(K(...B.level2.emperor), "#a03d2e", "E");
    tip(K(...B.level2.emperor), TITLES.emperor);
    chip(K(...B.level2.retreat), "#4a6b7a", "r");
    tip(K(...B.level2.retreat), TITLES.retreat);
    for (const [label, site] of [["c", "cellars"], ["b", "guard_barracks"],
                                 ["p", "peristyle"]]) {
      const [x, y] = B.level2[site];
      el("circle", { cx: cx(x) + 14, cy: cy(y) - 15, r: 8, fill: "#fffdf6",
                     stroke: "#3a2d20", "stroke-width": 1.4,
                     "pointer-events": "none" });
      el("text", { x: cx(x) + 14, y: cy(y) - 11.5, "text-anchor": "middle",
                   "font-family": "Verdana, sans-serif", "font-size": 10,
                   fill: "#3a2d20", "pointer-events": "none" }, svg, label);
    }
    svg.addEventListener("click", onBoardClick);
    svg.addEventListener("keydown", ev => {
      if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches(".reachable")) {
        ev.preventDefault();
        onBoardClick(ev);
      }
    });
  }

  function pawnFor(id) { return document.getElementById("pawn-" + id); }

  function placePawns() {
    for (const p of g.players) {
      if (pawnFor(p.id)) { setPawn(p.id, p.pos); continue; }
      const grp = el("g", { id: "pawn-" + p.id, class: "pawn",
                            "pointer-events": "none" });
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
    if (reducedMotion()) { setPawn(id, toK); return; }
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
      const marker = document.getElementById("treasure-" + k);
      const label = document.getElementById("district-" + k);
      if (!marker || !label) continue;
      marker.textContent = "✧";
      marker.setAttribute("fill", "#92713b");
      label.textContent = { pugio: "Pugio", pilum: "Pilum", galea: "Galea", scutum: "Scutum",
        gladius: "Gladius", lorica_segmentata: "Armor" }[item] || item;
      const mark = document.createElementNS(NS, "g");
      mark.id = "rv-" + k;
      mark.setAttribute("class", "revealchip");
      svg.appendChild(mark);
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
      const kind = p.kind === "human" ? "Human · this device" :
        "Bot · " + { balanced: "balanced", greedy: "collector", aggressive: "fighter", random: "wanderer" }[p.kind];
      d.setAttribute("aria-label", p.name + (isActive ? ", current turn" : ""));
      d.innerHTML =
        `<div class="pname"><span class="pawnchip" style="background:${COLORS[p.id]}"></span>${escapeHTML(p.name)}</div>
         <span class="player-kind">${kind}</span>
         <div class="pstats"><span aria-label="${p.glory} Glory">${glory}</span><span>Equipment <strong>${p.equipment.length}/6</strong></span></div>` +
         (g.phase === 2 ? `<div class="seals">Seals ${seals} <span class="hittag" aria-label="${p.hits} hits">${"✦".repeat(p.hits)}</span></div>` : "");
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
    document.getElementById("phase-label").textContent = g.phase === 1 ? "City · Level I" : "Palace · Level II";
    document.getElementById("city-step").classList.toggle("current", g.phase === 1);
    document.getElementById("palace-step").classList.toggle("current", g.phase === 2 && !g.winner);
    document.getElementById("emperor-step").classList.toggle("current", Boolean(g.winner));
    if (g.winner) {
      const p = E.player(g, g.winner);
      line.textContent = `${p.name} defeated the Emperor. Game over.`;
      return;
    }
    if (g.draw) { line.textContent = "The palace gates closed: a draw."; return; }
    const p = E.active(g);
    const phase = g.phase === 1 ? "the city" : "the palace";
    line.textContent = `Round ${g.round} in ${phase}: ${p.name}` +
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
    for (const k of (E.active(g).kind === "human" ? byDest.keys() : [])) {
      const c = svg.querySelector(`[data-k="${k}"]`);
      if (c) {
        c.classList.add("reachable");
        c.setAttribute("tabindex", "0");
        c.setAttribute("role", "button");
        c.setAttribute("aria-label", "Move to " + k + ". " + (c.querySelector("title")?.textContent || "Street space"));
      }
    }
    const p0 = E.active(g);
    if (p0.kind === "human") {
      const box0 = document.getElementById("actionbox");
      const hint = document.createElement("div");
      hint.className = "hint";
      hint.innerHTML = "You rolled <b>" + g.currentRoll.total +
        "</b>. Tap a lit circle to move. Blue letters hold treasure," +
        " green stars pay Glory, the gold X opens the gate, and ending" +
        " within two spaces of a rival lets you duel.";
      box0.appendChild(hint);
    } else {
      const hint = document.createElement("div");
      hint.className = "hint";
      hint.textContent = p0.name + " is planning a move…";
      document.getElementById("actionbox").appendChild(hint);
    }
  }

  function clearHighlights() {
    for (const c of svg.querySelectorAll(".reachable")) {
      c.classList.remove("reachable");
      c.removeAttribute("tabindex");
      c.removeAttribute("role");
      const title = c.querySelector("title");
      if (title) c.setAttribute("aria-label", title.textContent);
      else c.removeAttribute("aria-label");
    }
  }

  function onBoardClick(ev) {
    const c = ev.target.closest(".cell.reachable");
    if (!c || !g || g.winner || g.draw) return;
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
      case "guard_post": return "<b>Stand guard</b>: roll for Glory";
      case "duel": {
        const q = E.player(g, a.target);
        return `<b>Duel ${escapeHTML(q.name)}</b>`;
      }
      case "claim_checkpoint": return "<b>Open the gate</b>: first through";
      case "attempt_seal": return a.spend
        ? `<b>Buy the seal</b> at the ${siteNames[a.site]} (1 Glory)`
        : `<b>Roll for the seal</b> at the ${siteNames[a.site]}`;
      case "attack_emperor": return a.spend
        ? "<b>Powered strike</b>: pay 1 Glory for +2"
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
    document.getElementById("overline").textContent = g.winner
      ? E.player(g, g.winner).name + " rules the palace!"
      : "A draw in the palace.";
    document.getElementById("oversub").textContent =
      `Seed ${g.seed} · ${g.round} rounds · ` +
      g.players.map(p => `${p.name}: ${p.equipment.length} gear` +
        (g.phase === 2 ? `, ${p.seals.length} seals, ${p.hits} hits` : ""))
        .join(" · ");
    showOverlay("gameover");
  }

  /* ---------------- setup ---------------- */

  function buildSetup() {
    const seats = document.getElementById("seats");
    seats.innerHTML = "";
    for (const [pid, label] of Object.entries(SEATNAMES)) {
      const d = document.createElement("div");
      d.className = "seat";
      d.innerHTML =
        `<label for="name-${pid}"><span class="pawnchip" style="background:${COLORS[pid]}"></span>${label} gate</label>
         <input id="name-${pid}" value="Player ${label}" maxlength="16" autocomplete="off">
         <select id="kind-${pid}" aria-label="${label} gate player type">` +
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
      hideOverlay("gameover");
      startGame(false, true);
    };
    document.getElementById("setupbtn").onclick = () => {
      hideOverlay("gameover");
      showOverlay("setup");
    };
  }

  function startGame(watch, reuseSeats) {
    clearTimeout(botTimer);
    hideOverlay("setup");
    for (const rv of [...svg.querySelectorAll(".revealchip")]) rv.remove();
    for (const c of Object.values(B.districts)) {
      const marker = document.getElementById("treasure-" + K(...c));
      const label = document.getElementById("district-" + K(...c));
      if (marker) { marker.textContent = "?"; marker.setAttribute("fill", "#8c977b"); }
      if (label) label.textContent = "Hidden treasure";
    }
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

  // Rules overlay (full rulebook from rules.js).
  const rulesOverlay = document.getElementById("rules");
  document.getElementById("rulesbody").innerHTML =
    window.DIOCLET_RULES;
  document.getElementById("rulesbtn").onclick = () => showOverlay("rules");
  document.getElementById("setup-rulesbtn").onclick = () => showOverlay("rules");
  document.getElementById("rulesclose").onclick = () => hideOverlay("rules");
  rulesOverlay.addEventListener("click", ev => {
    if (ev.target === rulesOverlay) hideOverlay("rules");
  });
  document.addEventListener("keydown", ev => {
    if (ev.key === "Escape" && !rulesOverlay.classList.contains("hidden")) hideOverlay("rules");
    if (ev.key !== "Tab") return;
    const dialogs = [...document.querySelectorAll(".overlay:not(.hidden)")];
    const top = dialogs.find(d => d.id === "rules") || dialogs.at(-1);
    if (!top) return;
    const focusable = [...top.querySelectorAll("button, input, select, a[href], [tabindex='0']")];
    const first = focusable[0], last = focusable.at(-1);
    if (ev.shiftKey && (document.activeElement === first || document.activeElement === top)) {
      ev.preventDefault(); last?.focus();
    } else if (!ev.shiftKey && (document.activeElement === last || document.activeElement === top)) {
      ev.preventDefault(); first?.focus();
    }
  });

  document.getElementById("zoom-board").onclick = () => {
    const zoomed = document.getElementById("boardwrap").classList.toggle("is-zoomed");
    const button = document.getElementById("zoom-board");
    button.setAttribute("aria-pressed", String(zoomed));
    button.setAttribute("aria-label", zoomed ? "Show the whole board" : "Enlarge the board");
    button.title = zoomed ? "Show the whole board" : "Enlarge the board";
    button.textContent = zoomed ? "−" : "＋";
  };

  buildBoard();
  buildSetup();
  showOverlay("setup");
})();
