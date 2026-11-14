// The succession map: the second board, where the throne is contested.
// A single A4 landscape page: four city blocks around a crossing, gates
// at the compass points, the Peristyle at the centre, and the three
// faction meeting places on the street arms. Drawn as a companion sheet
// to the palace board: same paper, same pencil box, lighter hand - the
// map is a working chart, not a survey.
import { Sheet } from "../lib/core.mjs";
import { Artist } from "../lib/brush.mjs";
import { text, measure } from "../lib/letters.mjs";
import * as M from "../lib/motifs.mjs";
import * as A from "../lib/architecture.mjs";
import * as K from "../lib/marks.mjs";

const PI = Math.PI;
const w = (name, extra = {}) => ({ ...M.W[name], ...extra });

const GATE_LABELS = { P0: "GOLDEN GATE", P1: "SILVER GATE", P2: "BRONZE GATE", P3: "IRON GATE" };
const BLOCK_NAMES = { I: "MERCATVS", II: "BALNEAE", III: "TABERNAE", IV: "DOMVS" };
// The district plaque, body only; smaller than the palace's so each
// block keeps room for its buildings around it.
const PLAQUE = [22, 16];
const plaqueBox = (px, py) => M.tabulaBounds(px, py, PLAQUE[0], PLAQUE[1]);

const FACTION_LABELS = { army: "ARMY", officials: "OFFICIALS", elites: "CITY ELITES" };

export function renderSuccession(layout, { dpi = 300, seed = 400 } = {}) {
  const S = layout.succession;
  const [W0, H0] = S.size_mm;
  const sheet = new Sheet({ widthMm: W0, heightMm: H0, dpi, seed });
  const a = new Artist(sheet, { seed: 1 });
  const [gx, gy, gw, gh] = S.grid_mm;
  const G = { x0: gx, y0: gy, x1: gx + gw, y1: gy + gh };

  drawFrame(a, S);
  drawTitle(a, S);
  drawPaving(a, S);
  for (let i = 0; i < S.blocks.length; i++) drawBlock(a, S, i);

  // Play symbols.
  const special = new Set();
  const key = (p) => `${p[0].toFixed(2)},${p[1].toFixed(2)}`;
  for (const p of Object.values(S.gates)) special.add(key(p));
  for (const p of Object.values(S.factions)) special.add(key(p));
  special.add(key(S.checkpoint));
  for (const s of S.spaces) if (!special.has(key(s.mm))) K.streetSpace(a, s.mm[0], s.mm[1], 6.2);
  K.peristyle(a, S.checkpoint[0], S.checkpoint[1], 9.6);
  for (const p of Object.values(S.gates)) K.gateMark(a, p[0], p[1], 8.2);
  for (const [name, p] of Object.entries(S.factions)) {
    K.factionSite(a, p[0], p[1], name, 6.6);
    drawFactionLabel(a, name, p, S);
  }
  // A street circle sits directly south of the Peristyle, so its name
  // goes on a tag over the corner of block II, level with the ARMY and
  // OFFICIALS tags.
  tag(a, "PERISTYLE", S.checkpoint[0] + 10.5, S.checkpoint[1] + 12.5, 2.2, "left");
  for (const [pid, p] of Object.entries(S.gates)) drawGateLabel(a, pid, p, S, G);
  drawKey(a, S, G);

  const out = sheet.compose();
  sheet.release();
  return out;
}

function drawFrame(a, S) {
  a.rect(12, 8, 273, 196, w("bold", { width: 0.7, overshoot: 0.8 }));
  a.rect(13.6, 9.6, 269.8, 192.8, w("fine", { overshoot: 0.5 }));
  for (const [cx, cy] of [[12, 8], [285, 8], [12, 204], [285, 204]]) {
    M.lift(a, (c) => c.arc(cx, cy, 3.2, 0, PI * 2), 1);
    a.circle(cx, cy, 2.8, w("firm"));
    M.star(a, cx, cy, 2.1, { points: 8, inner: 0.45, weight: "firm", shade: false });
  }
}

function drawTitle(a, S) {
  const cx = S.size_mm[0] / 2;
  const cap = 6.4;
  const wd = text(a, "THE SUCCESSION MAP", cx, 21.5, cap, { style: "inscribed", medium: "charcoal", track: 0.06 });
  for (const s of [-1, 1]) {
    const x0 = cx + s * (wd / 2 + 3);
    M.laurelBranch(a, [[x0, 19], [x0 + s * 7, 17.4], [x0 + s * 13, 18.6]], { leafLen: 2.6, leafWid: 0.9, pairs: 4 });
  }
  text(a, "DIOCLETIAN'S PALACE · THE CONTEST FOR THE THRONE", cx, 26.8, 1.8, { medium: "graphite", weight: 1.05 });
}

function drawPaving(a, S) {
  const c = S.cell_mm;
  for (const s of S.spaces) {
    const [cx, cy] = s.mm;
    const x0 = cx - c / 2, y0 = cy - c / 2;
    for (let r = 0; r < 3; r++) {
      const yy = y0 + r * (c / 3);
      a.line([x0, yy], [x0 + c, yy], w("hair", { alpha: 0.2, bow: 0.05, wobble: 0.04 }));
      for (let k = 0; k < 3; k++) {
        const xx = x0 + (r % 2) * 2.75 + k * 5.5 + a.rng.gauss(0.4);
        if (xx > x0 + c) continue;
        a.line([xx, yy], [xx, yy + c / 3], w("hair", { alpha: 0.18, bow: 0 }));
      }
    }
  }
}

// Block plans, simpler than the palace's: this is a working map. The
// layout lists the blocks south-west, south-east, north-west, north-east
// (I to IV). Each plan builds around a plaque at the centre and keeps
// its buildings and trees off plaqueBox().
const PLANS = [
  // I, south-west: the market - stall rows north and south of an open court.
  (a, x, y, s, t) => {
    const box = plaqueBox(x + s / 2, y + t / 2);
    A.court(a, x + 2, y + 2, s - 4, t - 4, { colonnade: false });
    const n = 3, gap = 3, wd = (s - 10 - gap * (n - 1)) / n, hh = box.y0 - y - 4;
    for (let i = 0; i < n; i++) {
      A.hall(a, x + 5 + i * (wd + gap), y + 3, wd, hh, { ridge: "h" });
      A.hall(a, x + 5 + i * (wd + gap), y + t - 3 - hh, wd, hh, { ridge: "h" });
    }
    A.garden(a, x + 4, box.y0, s - 8, box.y1 - box.y0, 4, [box]);
    return [x + s / 2, y + t / 2];
  },
  // II, south-east: the baths - a hall to the west, the exercise court in
  // the middle, the round hot room and the plunge pool to the east.
  (a, x, y, s, t) => {
    const box = plaqueBox(x + s / 2, y + t / 2);
    A.hall(a, x + 2, y + 2, box.x0 - x - 4, t - 4, { ridge: "v" });
    A.court(a, box.x0 - 0.5, y + 2, box.x1 - box.x0 + 1, t - 4, { colonnade: true, spacing: 3.2 });
    const ex = box.x1 + 1.5, ew = x + s - 2 - ex;
    A.dome(a, ex + ew / 2, y + 2 + ew / 2, ew / 2 - 0.5, { ribs: 12 });
    M.waves(a, ex, y + t * 0.55, ew, t * 0.4, { density: 1 });
    a.rect(ex, y + t * 0.55, ew, t * 0.4, w("fine", { overshoot: 0.3 }));
    return [x + s / 2, y + t / 2];
  },
  // III, north-west: the shops - a row of tabernae, a yard behind.
  (a, x, y, s, t) => {
    const box = plaqueBox(x + s / 2, y + t / 2 + 2);
    const n = 4, gap = 2.5, wd = (s - 8 - gap * (n - 1)) / n;
    for (let i = 0; i < n; i++) A.hall(a, x + 4 + i * (wd + gap), y + 2, wd, box.y0 - y - 3, { ridge: "h" });
    A.court(a, x + 2, box.y0 - 0.5, s - 4, y + t - 2 - box.y0 + 0.5, { colonnade: false });
    A.garden(a, x + 4, box.y0 + 1, s - 8, box.y1 - box.y0 - 2, 4, [box]);
    return [x + s / 2, y + t / 2 + 2];
  },
  // IV, north-east: the town house - west wing, atrium, apsed dining
  // room and a store to the east.
  (a, x, y, s, t) => {
    const box = plaqueBox(x + s / 2, y + t / 2);
    A.hall(a, x + 2, y + 2, box.x0 - x - 4, t - 4, { ridge: "v" });
    A.court(a, box.x0 - 0.5, y + 2, box.x1 - box.x0 + 1, t - 4, { colonnade: true, spacing: 3.4 });
    const ex = box.x1 + 1.5, ew = x + s - 2 - ex;
    A.apseHall(a, ex, y + 2, ew, t * 0.46, "s");
    A.hall(a, ex, y + t * 0.66, ew, t * 0.34 - 2, { ridge: "v" });
    return [x + s / 2, y + t / 2];
  },
];

function drawBlock(a, S, index) {
  const [bx, by, bw, bh] = S.blocks[index];
  const ins = 1.6;
  const x = bx + ins, y = by + ins, s = bw - ins * 2, t = bh - ins * 2;
  const pts = [[x, y], [x + s, y], [x + s, y + t], [x, y + t]];
  A.castShadow(a, pts, 1.2);
  a.rect(x, y, s, t, w("bold", { width: 0.6, overshoot: 0.5 }));
  a.rect(x + 1.4, y + 1.4, s - 2.8, t - 2.8, w("hair", { overshoot: 0.35 }));
  const numeral = ["I", "II", "III", "IV"][index];
  const [px, py] = PLANS[index](a, x + 2.8, y + 2.8, s - 5.6, t - 5.6);
  M.tabula(a, px, py, PLAQUE[0], PLAQUE[1], { depth: 0.5 });
  text(a, numeral, px, py + 3.2, 8, { style: "inscribed", medium: "charcoal" });
  text(a, BLOCK_NAMES[numeral], px, py + 6.5, 1.6, { medium: "graphite", weight: 1.1, track: 0.15 });
}

function drawStreetNames(a, S, G) {
  // CARD O / DECVMANVS along the arms, tiny, in the margin.
  text(a, "CARDO", G.x0 - 8, S.checkpoint[1] + 12.5, 1.9, { medium: "graphite", weight: 1.05 });
  M.rotated(a, G.x1 + 9.5, S.checkpoint[1] - 12.5, -PI / 2, () => {
    text(a, "CARDO", 0, 1.25, 1.9, { medium: "graphite", weight: 1.05 });
  });
  M.rotated(a, S.checkpoint[0] - 12.5, G.y0 - 7.5, 0, () => {
    text(a, "DECVMANVS", 0, 1.25, 1.9, { medium: "graphite", weight: 1.05, align: "center" });
  });
  M.rotated(a, S.checkpoint[0] + 12.5, G.y1 + 9.5, 0, () => {
    text(a, "DECVMANVS", 0, 1.25, 1.9, { medium: "graphite", weight: 1.05, align: "center" });
  });
}

function drawGateLabel(a, pid, p, S, G) {
  const cap = 2.3;
  if (pid === "P0") text(a, GATE_LABELS.P0, p[0], G.y0 - 3.2, cap, { medium: "charcoal", weight: 1.1 });
  if (pid === "P2") text(a, GATE_LABELS.P2, p[0], G.y1 + 3.8, cap, { medium: "charcoal", weight: 1.1 });
  if (pid === "P1") M.rotated(a, G.x1 + 6.5, p[1] - 7.5, -PI / 2, () => {
    text(a, GATE_LABELS.P1, 0, 1.5, cap, { medium: "charcoal", weight: 1.1 });
  });
  if (pid === "P3") M.rotated(a, G.x0 - 6.5, p[1] + 7.5, PI / 2, () => {
    text(a, GATE_LABELS.P3, 0, 1.5, cap, { medium: "charcoal", weight: 1.1 });
  });
}

// A name on a small white plate with pointed ends, sized to the text.
function tag(a, label, x, y, cap, align = "center") {
  const wd = measure(label, cap);
  const cx = align === "left" ? x + wd / 2 : x;
  M.lift(a, (c) => {
    c.moveTo(cx - wd / 2 - 1, y - cap - 1);
    c.lineTo(cx + wd / 2 + 1, y - cap - 1);
    c.lineTo(cx + wd / 2 + 2.2, y - cap / 2);
    c.lineTo(cx + wd / 2 + 1, y + 1.2);
    c.lineTo(cx - wd / 2 - 1, y + 1.2);
    c.lineTo(cx - wd / 2 - 2.2, y - cap / 2);
    c.closePath();
  }, 0.95);
  text(a, label, cx, y, cap, { medium: "charcoal", weight: 1.1 });
}

function drawFactionLabel(a, name, p, S) {
  const label = FACTION_LABELS[name];
  // Elites: right of the circle, over the corner of block IV. Army and
  // officials: below their circles, over the top walls of II and I.
  if (name === "elites") tag(a, label, p[0] + 10.5, p[1] + 0.8, 2.2, "left");
  else tag(a, label, p[0], p[1] + 12.5, 2.2);
}

function drawKey(a, S, G) {
  // Two rows between the Bronze Gate label and the inner frame line
  // (y 202.4). Each row is centred on the page using the measured
  // width of its entries, so no label runs past the frame.
  const cap = 1.8, iconR = 2.3, pad = 2.2, between = 9;
  const y0 = G.y1 + 6;
  a.line([20, y0], [277, y0], w("fine"));
  const items = [
    ["gate", "GATE - RETURN HERE WHEN THE MAP OPENS"],
    ["faction", "FACTION MEETING PLACE - 1 PRESTIGE FOR SUPPORT"],
    ["peri", "PERISTYLE - PROCLAIM HERE"],
    ["space", "STREET SPACE - DUEL WINS PAY 1 PRESTIGE HERE"],
    ["block", "BUILDING - NO ENTRY"],
  ];
  const rows = [items.slice(0, 3), items.slice(3)];
  const cx = S.size_mm[0] / 2;
  let y = y0 + 4.4;
  for (const row of rows) {
    const widths = row.map(([, label]) => iconR * 2 + pad + measure(label, cap));
    const total = widths.reduce((u, v) => u + v, 0) + between * (row.length - 1);
    let x = cx - total / 2;
    row.forEach(([kind, label], i) => {
      const iconX = x + iconR;
      if (kind === "gate") K.gateMark(a, iconX, y, iconR);
      if (kind === "faction") K.factionSite(a, iconX, y, "officials", iconR);
      if (kind === "peri") K.peristyle(a, iconX, y, iconR);
      if (kind === "space") K.streetSpace(a, iconX, y, iconR - 0.2);
      if (kind === "block") {
        a.rect(iconX - iconR, y - iconR, iconR * 2, iconR * 2, w("bold", { width: 0.4 }));
        A.hall(a, iconX - iconR + 0.9, y - iconR + 0.9, iconR * 2 - 1.8, iconR * 2 - 1.8, { shadow: 0 });
      }
      text(a, label, x + iconR * 2 + pad, y + cap / 2, cap, { align: "left", medium: "graphite", weight: 1.05 });
      x += widths[i] + between;
    });
    y += 5.6;
  }
}
