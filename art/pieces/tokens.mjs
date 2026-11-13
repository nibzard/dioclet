// The token sheet: player pawns, Prestige coins, faction markers, the
// claim markers, and the round track - the same inventory as the
// black-and-white kit's tokens page, drawn in the same hand as the
// boards. One A4 portrait page; the kit PDF draws the cut guides on top.
import { Sheet } from "../lib/core.mjs";
import { Artist } from "../lib/brush.mjs";
import { text, measure } from "../lib/letters.mjs";
import * as M from "../lib/motifs.mjs";
import { factionEmblem } from "../lib/marks.mjs";

const PI = Math.PI;
const w = (name, extra = {}) => ({ ...M.W[name], ...extra });
const PW = 210, PH = 297;

// A pawn: a small standing figure - a citizen in a toga, seen from the
// front, with the player numeral on the base. Simple enough to read at
// 17 mm wide once cut and folded.
function pawn(a, cx, cy, h) {
  const u = h / 26;
  const top = cy - h / 2;
  a.smudge((c) => c.ellipse(cx + 2 * u, cy + h / 2, 7 * u, 1.6 * u, 0, 0, PI * 2), { alpha: 0.22, blur: 1.2 });
  // Head.
  a.circle(cx, top + 3.4 * u, 2.4 * u, w("firm"));
  M.tone(a, (c) => c.arc(cx + 0.8 * u, top + 3.4 * u, 2.1 * u, 0, PI * 2), [cx - 2.4 * u, top + 1 * u, 4.8 * u, 4.8 * u], 0.4, { angle: PI / 2.2 });
  // Shoulders and toga body, a bell shape.
  const body = [[cx - 3.2 * u, top + 7.2 * u], [cx + 3.2 * u, top + 7.2 * u],
    [cx + 4.4 * u, top + 15 * u], [cx + 5.4 * u, top + 21.6 * u], [cx - 5.4 * u, top + 21.6 * u], [cx - 4.4 * u, top + 15 * u]];
  M.tone(a, M.poly(body), M.bbox(body, 0.5), 0.3, { angle: PI / 2.6 });
  M.tone(a, M.poly([[cx + 1 * u, top + 6.4 * u], [cx + 3.2 * u, top + 7.2 * u], [cx + 4.4 * u, top + 15 * u], [cx + 5.4 * u, top + 21.6 * u],
    [cx + 2.6 * u, top + 21.6 * u], [cx + 2.2 * u, top + 13 * u]]), M.bbox(body, 0.5), 0.3, { angle: PI / 2.2 });
  a.polygon(body, w("firm", { overshoot: 0.12 }));
  a.line([cx - 3 * u, top + 7 * u], [cx + 3 * u, top + 7 * u], w("hair", { bow: 0.05 }));
  // A fold or two in the toga.
  a.stroke([[cx - 1.6 * u, top + 8 * u], [cx - 0.6 * u, top + 14 * u], [cx - 1.8 * u, top + 20 * u]], w("hair", { alpha: 0.4, bow: 0.15 }));
  a.stroke([[cx + 2.2 * u, top + 9 * u], [cx + 1.4 * u, top + 15 * u], [cx + 2.4 * u, top + 20 * u]], w("hair", { alpha: 0.4, bow: 0.15 }));
  // Base plinth.
  a.rect(cx - 6 * u, top + 21.6 * u, 12 * u, 3.2 * u, w("firm", { overshoot: 0.15 }));
  M.tone(a, (c) => c.rect(cx - 6 * u, top + 21.6 * u, 12 * u, 3.2 * u), [cx - 6 * u, top + 21.6 * u, 12 * u, 3.2 * u], 0.25, { angle: PI / 2 });
}

export function renderTokens(_layout, { dpi = 300, seed = 600 } = {}) {
  const sheet = new Sheet({ widthMm: PW, heightMm: PH, dpi, seed });
  const a = new Artist(sheet, { seed: 11 });

  // Page frame and title.
  a.rect(10, 8, 190, 281, w("bold", { width: 0.6, overshoot: 0.6 }));
  a.rect(11.4, 9.4, 187.2, 278.2, w("hair", { overshoot: 0.4 }));
  text(a, "TOKENS", PW / 2, 22, 6, { style: "inscribed", medium: "charcoal", track: 0.06 });
  text(a, "CUT OUT - FOLD THE PAWNS AND TAPE THEM UPRIGHT", PW / 2, 28, 2.0, { medium: "graphite", weight: 1.05 });
  a.line([24, 33], [PW - 24, 33], w("fine"));

  let y = 40;
  sectionLabel(a, "PLAYER PAWNS - FOLD IN HALF, TAPE OR GLUE", y);
  y += 8;
  const numerals = ["I", "II", "III", "IV"];
  numerals.forEach((num, i) => {
    const px = 20 + i * 44;
    for (const half of [0, 1]) {
      const hcx = px + 8.5 + half * 17;
      pawn(a, hcx, y + 13, 22);
      text(a, num, hcx, y + 24.4, 3.2, { style: "inscribed", medium: "charcoal" });
    }
    // Fold line down the middle, cut line around the box.
    a.line([px + 17, y - 1], [px + 17, y + 27], w("hair", { wobble: 0, alpha: 0.6 }));
    text(a, "FOLD", px + 17, y + 30, 1.3, { medium: "graphite", alpha: 0.6 });
    a.cutRect(px, y - 1, 34, 28);
  });
  y += 37;

  sectionLabel(a, "PRESTIGE COUNTERS - 16", y);
  y += 7;
  for (let i = 0; i < 16; i++) {
    const cx = 25 + (i % 8) * 22.5, cy = y + 7.5 + Math.floor(i / 8) * 19.5;
    M.coin(a, cx, cy, 7.4, { beads: true, worn: 0.15 });
    M.laurelWreath(a, cx, cy - 0.4, 4.6, { pairs: 5, leafLen: 2.4, leafWid: 0.8, gap: 0.5 });
    text(a, "I", cx, cy + 1.6, 3.6, { style: "inscribed", medium: "charcoal" });
    a.cutCircle(cx, cy, 7.8);
  }
  y += 47;

  sectionLabel(a, "FACTION SUPPORT MARKERS - 2 OF EACH", y);
  y += 7;
  const kinds = [["army", "ARMY"], ["officials", "OFFICIALS"], ["elites", "ELITES"]];
  kinds.forEach(([kind, label], i) => {
    for (let j = 0; j < 2; j++) {
      const cx = 33 + i * 58 + j * 20, cy = y + 7;
      M.coin(a, cx, cy, 7.4, { beads: false, worn: 0.15 });
      factionEmblem(a, cx, cy, 4.2, kind);
      a.cutCircle(cx, cy, 7.8);
    }
    text(a, label, 33 + i * 58 + 10, y + 18.5, 1.8, { medium: "graphite", weight: 1.05 });
  });
  y += 25;

  sectionLabel(a, "MARKERS", y);
  y += 7;
  M.tabula(a, 46, y + 11, 44, 20, { depth: 0.6 });
  a.cutRect(24, y + 1, 44, 20);
  text(a, "CLAIM", 46, y + 12.5, 5.0, { style: "inscribed", medium: "charcoal" });
  text(a, "PENDING", 46, y + 17.6, 1.9, { medium: "graphite", weight: 1.05 });
  M.tabula(a, 116, y + 11, 52, 20, { depth: 0.6 });
  a.cutRect(90, y + 1, 52, 20);
  M.laurelBranch(a, [[88, y + 8], [94, y + 6.8], [100, y + 7.4]], { leafLen: 2.4, leafWid: 0.8, pairs: 4 });
  text(a, "FIRST", 116, y + 10.5, 4.2, { style: "inscribed", medium: "charcoal" });
  text(a, "CHALLENGER", 116, y + 16.0, 2.3, { medium: "graphite", weight: 1.1, track: 0.1 });
  y += 30;

  sectionLabel(a, "ROUND AND PHASE TRACK", y);
  y += 6;
  trackRow(a, "CITY PHASE", y);
  y += 9.5;
  trackRow(a, "SUCCESSION PHASE", y);
  y += 11;
  text(a, "TRACK ROUNDS ONLY IF YOU USE THE 24-ROUND LIMITS.", PW / 2, y, 1.7, { medium: "graphite", alpha: 0.8 });

  const out = sheet.compose();
  sheet.release();
  return [["tokens-sheet.png", out]];
}

function sectionLabel(a, label, y) {
  const x = 20;
  text(a, label, x, y, 2.4, { align: "left", medium: "charcoal", weight: 1.2, track: 0.08 });
  const len = measure(label, 2.4, { spacing: 0.2 + 0.08 });
  a.line([x + len + 3, y - 1], [PW - 20, y - 1], w("hair", { alpha: 0.5 }));
}

function trackRow(a, label, y) {
  text(a, label, 20, y, 1.9, { align: "left", medium: "graphite", weight: 1.05 });
  for (let i = 0; i < 24; i++) {
    const bx = 78 + i * 5.0;
    a.rect(bx, y - 4.6, 4.2, 4.8, w("hair", { overshoot: 0.1 }));
    if ((i + 1) % 6 === 0) text(a, String(i + 1), bx + 2.1, y + 3.4, 1.6, { medium: "graphite", alpha: 0.75 });
  }
}
