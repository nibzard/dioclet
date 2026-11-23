/* Imperial Rivals: 305 AD - table UI over engine.js, succession-engine.js,
 * and succession-bots.js. One street grid, two boards: the palace map
 * with its six treasure entries, and the succession map with blind
 * faction cards and the Peristyle claim. */
(function () {
  "use strict";

  const B = window.DIOCLET_BOARD;
  const FACTIONS = { army: "Army", officials: "Imperial officials", elites: "City elites" };
  const LETTER = { army: "A", officials: "O", elites: "C" };
  const FACTIONCOLOR = { army: "#7a5a2e", officials: "#3f6f9e", elites: "#5f7a4a" };
  const GATES = { P0: "North · Golden", P1: "East · Silver", P2: "South · Bronze", P3: "West · Iron" };
  const ITEMS = { pugio: "Dagger", pilum: "Javelin", galea: "Helmet", scutum: "Shield",
    gladius: "Sword", lorica_segmentata: "Armor" };
  const E = window.DIOCLET_ENGINE;
  const BOTS = window.DIOCLET_BOTS;
  const CELL = 44, PAD = 36;
  const COLORS = { P0: "#5a3d6b", P1: "#b0532f", P2: "#5f7a4a", P3: "#3f6f9e" };
  const KINDS = [["human", "Human (this device)"], ["balanced", "Bot: balanced"],
                 ["greedy", "Bot: collector"], ["aggressive", "Bot: fighter"],
                 ["random", "Bot: wanderer"]];
  const C = B.succession;

  const svg = document.getElementById("board");
  const NS = "http://www.w3.org/2000/svg";
  let g = null, seed = 2026, botTimer = null, performing = false;

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
    const w = PAD * 2 + B.palaceMap.width * CELL, h = PAD * 2 + B.palaceMap.height * CELL;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    el("rect", { width: w, height: h, fill: "#efecdf", rx: 0 });
    el("rect", { x: 8, y: 8, width: w - 16, height: h - 16, rx: 0,
                 fill: "none", stroke: "#bdbea6", "stroke-width": 1.5 });
    el("rect", { x: 14, y: 14, width: w - 28, height: h - 28, rx: 0,
                 fill: "none", stroke: "#cfd0b9", "stroke-width": .8 });
    // Each declared footprint is one intact, non-walkable block.
    // District ownership is explicit; proximity must not assign cards.
    B.palaceMap.buildings.forEach(bld => {
      const left = PAD + bld.x0 * CELL + 3;
      const top = PAD + bld.y0 * CELL + 3;
      const width = (bld.x1 - bld.x0 + 1) * CELL - 6;
      const height = (bld.y1 - bld.y0 + 1) * CELL - 6;
      const district = [bld.district, B.palaceMap.treasureEntries[bld.district]];
      const group = el("g", { "pointer-events": "none", "aria-hidden": "true",
        class: "palace-block", "data-district": bld.district });
      el("rect", { x: left, y: top, width, height, rx: 0, fill: "#d9d5c2", stroke: "#b7b89d", "stroke-width": 1.3 }, group);
      // Inset masonry gives the blocks an architectural plan treatment.
      for (let x = left + 12; x < left + width - 8; x += CELL) {
        el("path", { d: `M${x} ${top + 7}v${height - 14}`, stroke: "#c7c7af", "stroke-width": 1 }, group);
      }
      for (let y = top + 12; y < top + height - 8; y += CELL) {
        el("path", { d: `M${left + 7} ${y}h${width - 14}`, stroke: "#c7c7af", "stroke-width": 1 }, group);
      }
      el("rect", { x: left + 20, y: top + 20, width: width - 40, height: height - 40, rx: 0,
        fill: "#e9e6d7", stroke: "#bbbea3", "stroke-width": 1 }, group);
      el("rect", { x: left + 26, y: top + 26, width: width - 52, height: height - 52, rx: 0,
        fill: "none", stroke: "#d0d1ba", "stroke-width": .8 }, group);
      if (district) {
        const midX = left + width / 2, midY = top + height / 2;
        // The treasure plate hides on the succession map: phase 2 has no
        // districts to explore.
        const plate = el("g", { class: "district-plate" }, group);
        el("text", { x: midX, y: midY - 43, "text-anchor": "middle", fill: "#7f866e",
          "font-family": "Verdana, sans-serif", "font-size": 8, "letter-spacing": 2 }, plate, "DISTRICT " + district[0]);
        el("rect", { x: midX - 20, y: midY - 30, width: 40, height: 48, rx: 0,
          fill: "#f3f0e4", stroke: "#a7af93", "stroke-width": 1 }, plate);
        el("text", { id: "treasure-" + K(...district[1]), x: midX, y: midY + 3,
          "text-anchor": "middle", fill: "#8c977b", "font-family": "Georgia, serif", "font-size": 29 }, plate, "?");
        el("text", { id: "district-" + K(...district[1]), x: midX, y: midY + 41,
          "text-anchor": "middle", fill: "#7d866d", "font-family": "Verdana, sans-serif",
          "font-size": 9 }, plate, "Hidden treasure");
      }
    });
    const streetLabel = (x, y, text) => el("text", { x, y,
      "text-anchor": "middle", fill: "#747d64", "font-family": "Verdana, sans-serif",
      "font-size": 8, "letter-spacing": 1, "pointer-events": "none" }, svg, text);
    streetLabel(cx(B.palaceMap.streets.cardo.coordinate), 26, "CARDO · N–S");
    streetLabel(cx(10), cy(B.palaceMap.streets.decumanus.coordinate) - 15, "DECUMANUS · E–W");
    streetLabel(w - 34, 26, "N ↑");
    for (let y = 0; y < B.palaceMap.height; y++) {
      for (let x = 0; x < B.palaceMap.width; x++) {
        if (B.palaceMap.blocked.some(c => c[0] === x && c[1] === y)) continue;
        const k = K(x, y);
        el("circle", { cx: cx(x), cy: cy(y), r: 13, fill: "#fbf9ee",
                       stroke: "#c0c4ab", "stroke-width": 1.5, "data-k": k,
                       class: "cell" });
      }
    }
    const TITLES = {
      gate: "Gate and start position",
      entry: "Treasure entry: stop here to take the card",
      checkpoint: "Checkpoint: first with all six items opens the succession",
      peristyle: "Peristyle: proclaim your claim with two factions behind you",
      post: "Guard post: roll " + B.prestige.guardMinRoll + " or more for " + B.prestige.guardReward + " Prestige",
      card: "Faction card: stop here and search to turn it over",
    };
    // Decorations never block clicks or hover: the street circle under
    // a chip owns the pointer and carries the tooltip.
    const chip = (k, fill, text, parent, siteClass) => {
      const [x, y] = at(k);
      // The interactive circle must cover the whole marker. Its outer
      // edge also keeps the available-move highlight visible.
      const target = svg.querySelector(`[data-k="${k}"]`);
      target.classList.add("site-cell", siteClass);
      el("circle", { cx: cx(x), cy: cy(y), r: 16.5, fill,
                     stroke: "#3a2d20", "stroke-width": 2.5,
                     "pointer-events": "none" }, parent);
      el("text", { x: cx(x), y: cy(y) + 5.5, "text-anchor": "middle",
                   "font-family": "Georgia, serif", "font-size": 16,
                   "font-weight": "bold", fill: "#fffdf6",
                   "pointer-events": "none" }, parent, text);
    };
    const tip = (k, text, phase = 1) => {
      const c = svg.querySelector(`[data-k="${k}"]`);
      if (!c) return;
      c.dataset[phase === 2 ? "successionTitle" : "palaceTitle"] = text;
    };
    const palaceLayer = el("g", { id: "palace-markers" });
    for (const [p, c] of Object.entries(B.palaceMap.gates)) {
      chip(K(...c), "#5a3d6b", { P0: "N", P1: "E", P2: "S", P3: "W" }[p], palaceLayer, "palace-site");
      tip(K(...c), TITLES.gate + " (" + p + ")");
    }
    for (const [n, c] of Object.entries(B.palaceMap.treasureEntries)) {
      chip(K(...c), "#3f6f9e", n, palaceLayer, "palace-site");
      tip(K(...c), TITLES.entry + " (" + n + ")");
    }
    chip(K(...B.palaceMap.checkpoint), "#c9972b", "X", palaceLayer, "palace-site");
    tip(K(...B.palaceMap.checkpoint), TITLES.checkpoint);
    for (const c of B.palaceMap.guardPosts) {
      chip(K(...c), "#5f7a4a", "*", palaceLayer, "palace-site");
      tip(K(...c), TITLES.post);
    }
    // The succession map: gates move (the south gate trades places),
    // the Peristyle replaces the checkpoint, posts relocate, and six
    // face-down faction cards wait on the card spaces.
    const successionLayer = el("g", { id: "succession-markers", display: "none" });
    for (const [p, c] of Object.entries(B.successionMap.gates)) {
      chip(K(...c), "#5a3d6b", { P0: "N", P1: "E", P2: "S", P3: "W" }[p], successionLayer, "succession-site");
      tip(K(...c), TITLES.gate + " on the succession map (" + p + ")", 2);
    }
    chip(K(...B.successionMap.checkpoint), "#c9972b", "♛", successionLayer, "succession-site");
    tip(K(...B.successionMap.checkpoint), TITLES.peristyle, 2);
    for (const c of B.successionMap.guardPosts) {
      chip(K(...c), "#5f7a4a", "*", successionLayer, "succession-site");
      tip(K(...c), TITLES.post, 2);
    }
    for (const c of B.successionMap.cardSpaces) {
      const k = K(...c);
      const card = el("g", { id: "site-" + k, "pointer-events": "none" }, successionLayer);
      el("rect", { x: cx(c[0]) - 10.5, y: cy(c[1]) - 10.5, width: 21, height: 21,
        fill: "#203d35", stroke: "#f3f0e8", "stroke-width": 1.2 }, card);
      el("text", { id: "sitetext-" + k, x: cx(c[0]), y: cy(c[1]) + 6, "text-anchor": "middle",
        fill: "#fffdf6", "font-family": "Georgia, serif", "font-size": 15,
        "font-weight": "bold" }, card, "?");
      svg.querySelector(`[data-k="${k}"]`).classList.add("site-cell", "succession-site");
      tip(k, TITLES.card, 2);
    }
    const [px, py] = B.successionMap.checkpoint;
    const claim = el("g", { id: "claim-marker", display: "none", "pointer-events": "none", "aria-hidden": "true" });
    el("rect", { x: cx(px) - 24, y: cy(py) - 24, width: 48, height: 48,
      fill: "none", stroke: "#a4772d", "stroke-width": 3 }, claim);
    svg.addEventListener("click", onBoardClick);
    svg.addEventListener("keydown", ev => {
      if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches(".reachable")) {
        ev.preventDefault();
        onBoardClick(ev);
      }
    });
  }

  let boardPhase = null;
  function renderBoardPhase() {
    const phase = g ? g.phase : 1;
    if (boardPhase === phase) return;
    boardPhase = phase;
    const succession = phase === 2;
    document.getElementById("palace-markers").setAttribute("display", succession ? "none" : "inline");
    document.getElementById("succession-markers").setAttribute("display", succession ? "inline" : "none");
    for (const plate of svg.querySelectorAll(".district-plate"))
      plate.setAttribute("display", succession ? "none" : "inline");
    document.getElementById("checkpoint-key").textContent = succession ? "Peristyle · claim" : "Checkpoint";
    for (const c of svg.querySelectorAll(".cell")) {
      const big = c.classList.contains(succession ? "succession-site" : "palace-site");
      c.setAttribute("r", big ? "20" : "13");
      const text = (succession && c.dataset.successionTitle) || c.dataset.palaceTitle;
      c.querySelector("title")?.remove();
      if (text) {
        el("title", {}, c, text);
        c.setAttribute("aria-label", text);
      } else c.removeAttribute("aria-label");
    }
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
                   "font-weight": "bold" }, grp, String(p.index + 1));
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
    const steps = E.path(fromK, toK, E.mapFor(g).graph);
    if (steps.length < 2) { setPawn(id, toK); return; }
    for (const step of steps.slice(1)) {
      setPawn(id, step);
      await new Promise(r => setTimeout(r, 110));
    }
  }

  function showRevealed() {
    for (const [name, item] of Object.entries(g.revealed)) {
      const k = K(...B.palaceMap.treasureEntries[name]);
      const marker = document.getElementById("treasure-" + k);
      const label = document.getElementById("district-" + k);
      if (!marker || marker.dataset.item === item) continue;
      marker.dataset.item = item;
      marker.textContent = "✧";
      marker.setAttribute("fill", "#92713b");
      label.textContent = ITEMS[item] || item;
    }
  }

  // Turn the six face-down faction cards as players search them. A
  // searched space shows its faction letter or an empty street mark.
  function showSites() {
    const revealed = g.factionSitesRevealed;
    for (const c of B.successionMap.cardSpaces) {
      const k = K(...c);
      const card = document.getElementById("site-" + k);
      const box = card.querySelector("rect");
      const text = document.getElementById("sitetext-" + k);
      const cell = svg.querySelector(`[data-k="${k}"]`);
      if (!revealed || !(k in revealed)) {
        box.setAttribute("fill", "#203d35");
        text.textContent = "?";
        cell.dataset.successionTitle = "Faction card: stop here and search to turn it over";
      } else {
        const faction = revealed[k];
        if (faction) {
          box.setAttribute("fill", FACTIONCOLOR[faction]);
          text.textContent = LETTER[faction];
          cell.dataset.successionTitle = FACTIONS[faction] + " support: spend " +
            C.supportCost + " Prestige here for their backing";
        } else {
          box.setAttribute("fill", "#8a8d7f");
          text.textContent = "–";
          cell.dataset.successionTitle = "Searched: no faction deals from this space";
        }
      }
    }
    if (boardPhase === 2) for (const c of svg.querySelectorAll(".cell")) {
      const text = c.dataset.successionTitle;
      if (text) {
        c.querySelector("title")?.remove();
        el("title", {}, c, text);
        c.setAttribute("aria-label", text);
      }
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
      const kind = p.kind === "human" ? "Human · this device" :
        "Bot · " + ({ balanced: "balanced", greedy: "collector", aggressive: "fighter", random: "wanderer" }[p.kind] || p.kind);
      d.setAttribute("aria-label", p.name + (isActive ? ", current turn" : ""));
      const badges = p.support.map(f =>
        `<span class="fbadge" title="${escapeHTML(FACTIONS[f])}">${LETTER[f]}</span>`).join("");
      const gear = p.equipment.map(i => ITEMS[i] || i).join(", ");
      d.innerHTML = `<div class="pname"><span class="pawnchip" style="background:${COLORS[p.id]}"></span>${escapeHTML(p.name)}</div>
        <span class="player-kind">${kind}<br>${GATES[p.gateId]}</span>
        <div class="pstats"><span>Prestige <strong>${p.prestige}${B.prestige.cap == null ? "" : "/" + B.prestige.cap}</strong></span><span>Gear <strong>${p.equipment.length}/6</strong></span></div>
        <div class="gear-list"><strong>${p.equipment.length}/6 gear</strong>${gear ? " · " + escapeHTML(gear) : ""}</div>
        <div class="support-list"><strong>${p.support.length}/${C.requiredSupport} support</strong> ${badges || "· none yet"}</div>`;
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
      if (/duel|defeats|loses/.test(line)) d.className = "evt";
      if (/Prestige/.test(line)) d.className = "prestige";
      box.appendChild(d);
    }
    box.scrollTop = box.scrollHeight;
  }

  function renderTurnline() {
    renderBoardPhase();
    const line = document.getElementById("turnline");
    document.getElementById("phase-label").textContent = g.phase === 1 ? "Palace · Phase I" : "Succession · Phase II";
    document.getElementById("palace-step").classList.toggle("current", g.phase === 1);
    document.getElementById("succession-step").classList.toggle("current", g.phase === 2 && !g.winner && !g.pendingClaim);
    document.getElementById("emperor-step").classList.toggle("current", Boolean(g.winner || g.pendingClaim));
    if (g.winner) {
      const p = E.player(g, g.winner);
      line.textContent = `${p.name} is acclaimed emperor. Game over.`;
      return;
    }
    renderClaim();
    if (g.draw) { line.textContent = "No claim prevailed before the deadline. A draw."; return; }
    const p = E.active(g);
    const phase = g.phase === 1 ? "the palace" : "the succession";
    line.textContent = `Round ${g.round} in ${phase}: ${p.name}` +
      (p.kind === "human" ? " (your turn)" : " is thinking…");
  }

  function renderClaim() {
    const claim = g.pendingClaim;
    const marker = document.getElementById("claim-marker");
    marker.setAttribute("display", claim ? "inline" : "none");
    const box = document.getElementById("claim-status");
    box.hidden = !claim;
    if (!claim) { box.textContent = ""; return; }
    const name = E.player(g, claim.player).name;
    const left = Math.max(0, claim.round + C.claimWindowRounds - g.round);
    box.textContent = name + " proclaims at the Peristyle. The claim holds for " +
      left + (left === 1 ? " more full round" : " more full rounds") +
      " unless a rival wins a contest duel. A beaten claimant pays 1 Prestige and walks back to the gate.";
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
      hint.innerHTML = "You rolled <b>" + g.currentRoll.total + "</b>. Tap a lit circle." +
        (g.pendingClaim ? " <b>A rival's claim stands.</b> Win a contest duel to cancel it before the window closes."
          : g.phase === 1 ? " Collect equipment in the blocks and stand guard for Prestige. Six items open the succession."
          : " Search a faction card, buy support at a revealed card, then proclaim at the Peristyle.");
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
    const legal = byDest.get(k);
    if (!legal) return;
    // Collecting and searching have no cost. Walking past an available
    // card adds no useful option; keep alternatives such as dueling.
    const pointless = a => a.kind === "explore" || a.kind === "search_site";
    const list = legal.some(pointless) ? legal.filter(a => a.kind !== "move") : legal;
    if (list.length === 1) { humanAct(list[0]); return; }
    const box = document.getElementById("choice-actions");
    box.replaceChildren();
    document.getElementById("choice-context").textContent =
      c.querySelector("title")?.textContent || "Street space " + k;
    for (const a of list) {
      const b = document.createElement("button");
      b.className = "choice";
      b.innerHTML = describe(a);
      b.onclick = () => {
        hideOverlay("choice-dialog");
        humanAct(a);
      };
      box.appendChild(b);
    }
    showOverlay("choice-dialog");
    box.querySelector("button").focus();
  }

  function describe(a) {
    switch (a.kind) {
      case "move": return "Just <b>walk</b> here";
      case "explore": {
        const known = g.revealed[a.dest];
        return "<b>Take the treasure</b>" + (known ? " (" + escapeHTML(ITEMS[known] || known) + ")" : "");
      }
      case "inspect": return a.site
        ? "<b>Consult the helmet</b> · reveal card space " + a.site
        : "<b>Consult the helmet</b> · reveal district " + a.district;
      case "search_site": return "<b>Search the card space</b> · turn the faction card";
      case "guard_post": return "<b>Stand guard</b>: roll " + B.prestige.guardMinRoll + " or more for " + B.prestige.guardReward + " Prestige";
      case "gain_support": return "<b>Secure " + FACTIONS[a.faction] + " support</b> · " + C.supportCost + " Prestige";
      case "proclaim": return "<b>Proclaim your claim</b> · holds for " + C.claimWindowRounds + " full rounds";
      case "maintain_claim": return "<b>Hold the Peristyle</b> · keep your claim";
      case "duel": {
        const q = E.player(g, a.target);
        const contest = g.pendingClaim && g.pendingClaim.player === a.target;
        const label = contest ? "Contest " + escapeHTML(q.name) + "’s claim" : "Duel " + escapeHTML(q.name);
        const fee = contest ? (a.contest_cost || 0) : 0;
        return "<b>" + label + "</b> · " + fee + " Prestige fee · 1d6 each, best item applies";
      }
      case "claim_checkpoint": return "<b>Claim the checkpoint</b> · first with all six items";
    }
    return a.kind;
  }

  async function humanAct(a) {
    document.getElementById("actionbox").innerHTML = "";
    await perform(a);
  }

  async function perform(a) {
    if (performing) return;
    performing = true;
    try {
      const p = E.active(g), from = p.pos;
      clearHighlights();
      const rec = E.applyAction(g, a);
      renderBoardPhase();
      await animatePawn(p.id, from, a.dest);
      // A contest or the phase change can also move other pawns.
      for (const q of g.players) setPawn(q.id, q.pos);
      renderDice(rec.dice);
      showRevealed();
      showSites();
      renderPlayers(); renderLog(); renderTurnline();
      if (g.winner || g.draw) { showGameOver(); return; }
      refreshActions(); renderDice(); scheduleBot();
    } finally { performing = false; }
  }

  function scheduleBot() {
    const p = E.active(g);
    if (p.kind === "human" || g.winner || g.draw) return;
    clearTimeout(botTimer);
    botTimer = setTimeout(async () => {
      const acts = E.legalActions(g);
      const rng = () => g.rng();
      const a = BOTS.choose(p.kind === "human" ? "balanced" : p.kind, g, acts, rng);
      await perform(a);
    }, 650);
  }

  function showGameOver() {
    document.getElementById("overline").textContent = g.winner
      ? E.player(g, g.winner).name + " is acclaimed emperor!"
      : "A draw in the succession.";
    document.getElementById("oversub").textContent =
      `Seed ${g.seed} · ${g.round} rounds · ` +
      g.players.map(p => `${p.name}: ${p.equipment.length} gear` +
        `, ${p.support.length} support, ${p.prestige} Prestige`)
        .join(" · ");
    showOverlay("gameover");
  }

  /* ---------------- setup ---------------- */

  function buildSetup() {
    const seats = document.getElementById("seats");
    seats.innerHTML = "";
    for (const [index, pid] of ["P0", "P1", "P2", "P3"].entries()) {
      const label = "Player " + (index + 1);
      const d = document.createElement("div");
      d.className = "seat";
      d.innerHTML =
        `<label for="name-${pid}"><span class="pawnchip" style="background:${COLORS[pid]}"></span>${label}</label>
         <input id="name-${pid}" value="${label}" maxlength="16" autocomplete="off">
         <select id="kind-${pid}" aria-label="${label} player type">` +
        KINDS.map(([v, t]) =>
          `<option value="${v}">${t}</option>`)
          .join("") + `</select><select class="manual-gate" id="gate-${pid}" aria-label="${label} starting gate">` +
          Object.entries(GATES).map(([id, text]) => `<option value="${id}" ${id === pid ? "selected" : ""}>${text}</option>`).join("") +
          `</select><span class="gate-preview" id="gate-preview-${pid}"></span>`;
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
      if (g.setupOptions && g.setupOptions.gateMode === "rotation") g.setupOptions.gateRotation = (g.setupOptions.gateRotation + 1) % 4;
      startGame(false, true);
    };
    document.getElementById("setupbtn").onclick = () => {
      hideOverlay("gameover");
      showOverlay("setup");
    };
  }

  function setupOptions() {
    const mode = document.getElementById("gate-mode").value;
    return { gateMode: mode,
      gateOrder: mode === "manual" ? ["P0", "P1", "P2", "P3"].map(id => document.getElementById("gate-" + id).value) : undefined,
      gateRotation: Number(document.getElementById("gate-rotation").value) };
  }

  function previewAssignments() {
    const options = setupOptions(), ids = ["P0", "P1", "P2", "P3"];
    for (const id of ids) document.getElementById("gate-" + id).hidden = options.gateMode !== "manual";
    document.getElementById("rotation-label").hidden = options.gateMode !== "rotation";
    const error = document.getElementById("setup-error");
    try {
      const preview = E.newGame(Number(document.getElementById("seed").value) || 2026,
        ids.map(id => ({ id, name: id, kind: "human" })), options);
      for (const p of preview.players) document.getElementById("gate-preview-" + p.id).textContent = "Starts at " + GATES[p.gateId];
      error.textContent = "";
      document.getElementById("startbtn").disabled = false;
      document.getElementById("watchbtn").disabled = false;
    } catch (err) {
      error.textContent = "Choose four different starting gates.";
      document.getElementById("startbtn").disabled = true;
      document.getElementById("watchbtn").disabled = true;
    }
  }

  function startGame(watch, reuseSeats) {
    clearTimeout(botTimer);
    hideOverlay("setup");
    for (const rv of [...svg.querySelectorAll(".revealchip")]) rv.remove();
    for (const [name, c] of Object.entries(B.palaceMap.treasureEntries)) {
      const k = K(...c);
      const marker = document.getElementById("treasure-" + k);
      const label = document.getElementById("district-" + k);
      if (marker) {
        marker.textContent = "?";
        marker.setAttribute("fill", "#8c977b");
        delete marker.dataset.item;
      }
      if (label) label.textContent = "Hidden treasure";
    }
    const seats = ["P0", "P1", "P2", "P3"].map(pid => ({
      id: pid,
      kind: watch ? "balanced" :
        (reuseSeats ? g.players.find(p => p.id === pid).kind
          : document.getElementById("kind-" + pid).value),
      name: watch ? "Player " + (Number(pid[1]) + 1) :
        (reuseSeats ? g.players.find(p => p.id === pid).name
          : (document.getElementById("name-" + pid).value || pid)),
    }));
    if (watch) seats[1].kind = "greedy";
    const options = reuseSeats ? { ...g.setupOptions } : setupOptions();
    g = E.newGame(seed, seats, options);
    g.setupOptions = options;
    g.log.push("The palace gates open. Six treasures wait in the blocks.");
    placePawns();
    renderPlayers(); renderDice(); renderLog(); renderTurnline();
    showSites();
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
  const choiceDialog = document.getElementById("choice-dialog");
  document.getElementById("choice-cancel").onclick = () => hideOverlay("choice-dialog");
  choiceDialog.addEventListener("click", ev => {
    if (ev.target === choiceDialog) hideOverlay("choice-dialog");
  });
  document.addEventListener("keydown", ev => {
    if (ev.key === "Escape") {
      if (!rulesOverlay.classList.contains("hidden")) hideOverlay("rules");
      else if (!choiceDialog.classList.contains("hidden")) hideOverlay("choice-dialog");
    }
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
  renderBoardPhase();
  buildSetup();
  for (const element of document.querySelectorAll("#setup select, #seed")) element.addEventListener("change", previewAssignments);
  document.getElementById("seed").addEventListener("input", previewAssignments);
  previewAssignments();
  showOverlay("setup");
})();
