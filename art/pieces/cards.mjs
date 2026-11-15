// The six equipment cards, miniature catalogue plates. Each card is
// 55x75 mm with a 2 mm bleed margin around it (the PNG is 59x79) so the
// family can glue them back to back without a white rim.
import { Sheet } from "../lib/core.mjs";
import { Artist } from "../lib/brush.mjs";
import { text, wrap, measure } from "../lib/letters.mjs";
import * as M from "../lib/motifs.mjs";
import { DEVICES } from "../lib/devices.mjs";

const PI = Math.PI;
const w = (name, extra = {}) => ({ ...M.W[name], ...extra });
const BLEED = 2;

const ROMAN = ["I", "II", "III", "IV", "V", "VI"];

export function renderCards(layout, { dpi = 300, seed = 500 } = {}) {
  const [cw, ch] = layout.cards.size_mm;
  const out = [];
  layout.cards.items.forEach((item, i) => {
    const sheet = new Sheet({ widthMm: cw + BLEED * 2, heightMm: ch + BLEED * 2, dpi, seed: seed + i * 17 });
    const a = new Artist(sheet, { seed: 7 + i });
    drawCard(a, item, i, cw, ch, BLEED);
    const canvas = sheet.compose();
    sheet.release();
    out.push([`card-${i + 1}-${item.icon}.png`, canvas]);
  });
  return out;
}

export { renderCardBack as renderBack };

function drawCard(a, item, index, cw, ch, bleed) {
  const cx = bleed + cw / 2;
  const y0 = bleed, y1 = bleed + ch;

  // Double frame with corner rosettes.
  a.rect(bleed + 2.4, y0 + 2.4, cw - 4.8, ch - 4.8, w("bold", { width: 0.55, overshoot: 0.5 }));
  a.rect(bleed + 3.6, y0 + 3.6, cw - 7.2, ch - 7.2, w("hair", { overshoot: 0.4 }));
  for (const [rx, ry] of [[bleed + 2.4, y0 + 2.4], [bleed + cw - 2.4, y0 + 2.4], [bleed + 2.4, y1 - 2.4], [bleed + cw - 2.4, y1 - 2.4]]) {
    M.lift(a, (c) => c.arc(rx, ry, 2.6, 0, PI * 2), 1);
    a.circle(rx, ry, 2.1, w("firm"));
    M.star(a, rx, ry, 1.5, { points: 8, inner: 0.45, weight: "firm", shade: false });
  }

  // Title across the full frame width. A name too long for one line at
  // the standard size (Lorica Segmentata) breaks onto two lines.
  const name = item.name.toUpperCase();
  const titleW = cw - 12, track = 0.05;
  const fits = (str, cap) => measure(str, cap, { spacing: 0.2 + track }) <= titleW;
  let ruleY = y0 + 14.4;
  if (fits(name, 4.6)) {
    text(a, name, cx, y0 + 10.5, 4.6, { style: "inscribed", medium: "charcoal", track });
  } else {
    const words = name.split(" ");
    const lines = [words.slice(0, -1).join(" "), words[words.length - 1]];
    let cap = 3.6;
    while (!lines.every((ln) => fits(ln, cap))) cap -= 0.1;
    text(a, lines[0], cx, y0 + 7.6, cap, { style: "inscribed", medium: "charcoal", track });
    text(a, lines[1], cx, y0 + 7.6 + cap + 0.6, cap, { style: "inscribed", medium: "charcoal", track });
    ruleY = y0 + 15.8;
  }
  // The rule carries the index coin at its centre, laurel either side.
  const coinR = 3.3;
  a.line([bleed + 8, ruleY], [cx - coinR - 1.2, ruleY], w("fine", { bow: 0.1 }));
  a.line([cx + coinR + 1.2, ruleY], [bleed + cw - 8, ruleY], w("fine", { bow: 0.1 }));
  M.laurelBranch(a, [[cx - 15, ruleY + 3], [cx - 10, ruleY + 2], [cx - coinR - 1.6, ruleY + 2.4]], { leafLen: 2.0, leafWid: 0.7, pairs: 3, berries: false });
  M.laurelBranch(a, [[cx + 15, ruleY + 3], [cx + 10, ruleY + 2], [cx + coinR + 1.6, ruleY + 2.4]], { leafLen: 2.0, leafWid: 0.7, pairs: 3, berries: false });
  M.coin(a, cx, ruleY, coinR, { beads: true, worn: 0.1 });
  text(a, ROMAN[index], cx, ruleY + 1.1, 2.3, { style: "inscribed", medium: "charcoal" });

  // The arch window: a niche with a hatched soffit and a sill.
  const wcx = cx, sill = y0 + 58.5, topY = y0 + 21.5;
  const aw = 15.5, springY = sill - 16;
  const opening = (c) => {
    c.moveTo(wcx - aw, sill);
    c.lineTo(wcx - aw, springY);
    c.arc(wcx, springY, aw, aw, PI, 2 * PI);
    c.lineTo(wcx + aw, sill);
    c.closePath();
  };
  // Wall around the niche: a light tone, so the object reads on it.
  M.tone(a, (c) => { c.rect(bleed + 6, topY, cw - 12, sill - topY); }, [bleed + 6, topY, cw - 12, sill - topY], 0.16, { angle: PI / 4 });
  M.lift(a, opening, 0.92);
  // The arch drawn firm, with radiating soffit joints.
  a.line([wcx - aw, sill], [wcx - aw, springY], w("firm"));
  a.line([wcx + aw, sill], [wcx + aw, springY], w("firm"));
  a.stroke((() => { const pts = []; for (let i = 0; i <= 20; i++) { const t = PI + (i / 20) * PI; pts.push([wcx + Math.cos(t) * aw, springY + Math.sin(t) * aw]); } return pts; })(), w("firm"));
  for (let i = 1; i < 6; i++) {
    const t = PI + (i / 6) * PI;
    a.line([wcx + Math.cos(t) * (aw - 2.6), springY + Math.sin(t) * (aw - 2.6)], [wcx + Math.cos(t) * aw, springY + Math.sin(t) * aw], w("hair", { bow: 0 }));
  }
  a.line([wcx - aw - 1.4, sill], [wcx + aw + 1.4, sill], w("firm", { bow: 0.06 }));
  a.line([wcx - aw - 0.8, sill - 1.1], [wcx + aw + 0.8, sill - 1.1], w("hair", { bow: 0.06 }));

  // The device itself, standing on the sill.
  (DEVICES[item.icon] || DEVICES.dagger)(a, wcx, (topY + sill) / 2 + 4, 30);

  // Ability text on a lifted plate at the foot.
  const plateY0 = y1 - 14.5, plateY1 = y1 - 4.5;
  M.lift(a, (c) => c.rect(bleed + 6, plateY0, cw - 12, plateY1 - plateY0), 0.95);
  a.rect(bleed + 6, plateY0, cw - 12, plateY1 - plateY0, w("hair", { overshoot: 0.3 }));
  const cap = 2.1;
  const lines = wrap(item.text.toUpperCase(), cap, cw - 17);
  const ty0 = (plateY0 + plateY1) / 2 - ((lines.length - 1) * cap * 1.7) / 2 + cap / 2 - 0.4;
  lines.forEach((ln, i) => text(a, ln, cx, ty0 + i * cap * 1.7, cap, { medium: "graphite", weight: 1.05 }));

  // The cut line sits at the bleed inset.
  a.cutRect(bleed, bleed, cw, ch);
}

// One shared back: a wreath around the palace monogram, so every card
// reads the same from the reverse.
export function renderCardBack(layout, { dpi = 300, seed = 560 } = {}) {
  const [cw, ch] = layout.cards.size_mm;
  const sheet = new Sheet({ widthMm: cw + BLEED * 2, heightMm: ch + BLEED * 2, dpi, seed });
  const a = new Artist(sheet, { seed: 23 });
  const cx = BLEED + cw / 2, cy = BLEED + ch / 2;
  a.rect(BLEED + 2.4, BLEED + 2.4, cw - 4.8, ch - 4.8, w("bold", { width: 0.55, overshoot: 0.5 }));
  a.rect(BLEED + 3.6, BLEED + 3.6, cw - 7.2, ch - 7.2, w("hair", { overshoot: 0.4 }));
  for (const [rx, ry] of [[BLEED + 2.4, BLEED + 2.4], [BLEED + cw - 2.4, BLEED + 2.4], [BLEED + 2.4, BLEED + ch - 2.4], [BLEED + cw - 2.4, BLEED + ch - 2.4]]) {
    M.lift(a, (c) => c.arc(rx, ry, 2.6, 0, Math.PI * 2), 1);
    a.circle(rx, ry, 2.1, w("firm"));
    M.star(a, rx, ry, 1.5, { points: 8, inner: 0.45, weight: "firm", shade: false });
  }
  M.laurelWreath(a, cx, cy - 4, 19, { pairs: 10, leafLen: 6, leafWid: 1.9, gap: 0.55 });
  text(a, "IR", cx, cy - 1.2, 8.5, { style: "inscribed", medium: "charcoal" });
  // The brand under the wreath, clear of the leaves.
  text(a, "IMPERIAL RIVALS", cx, cy + 25, 2.6, { medium: "charcoal", weight: 1.15, track: 0.12 });
  text(a, "305 AD", cx, cy + 29.4, 2.0, { medium: "graphite", track: 0.12 });
  a.cutRect(BLEED, BLEED, cw, ch);
  const canvas = sheet.compose();
  sheet.release();
  return canvas;
}

// ---------------------------------------------------------------------------
// The six faction cards for the succession map: three factions and three
// empty streets, and their shared back. Same size, frame and bleed as the
// treasure cards; the back is clearly different, so the two decks never
// mix: a large '?' over the three faction devices.
import * as K from "../lib/marks.mjs";

const FACTION_KIND = { shield: "army", column: "officials", laurel: "elites" };

function cardFrame(a, cw, ch) {
  const y0 = BLEED, y1 = BLEED + ch;
  a.rect(BLEED + 2.4, y0 + 2.4, cw - 4.8, ch - 4.8, w("bold", { width: 0.55, overshoot: 0.5 }));
  a.rect(BLEED + 3.6, y0 + 3.6, cw - 7.2, ch - 7.2, w("hair", { overshoot: 0.4 }));
  for (const [rx, ry] of [[BLEED + 2.4, y0 + 2.4], [BLEED + cw - 2.4, y0 + 2.4], [BLEED + 2.4, y1 - 2.4], [BLEED + cw - 2.4, y1 - 2.4]]) {
    M.lift(a, (c) => c.arc(rx, ry, 2.6, 0, PI * 2), 1);
    a.circle(rx, ry, 2.1, w("firm"));
    M.star(a, rx, ry, 1.5, { points: 8, inner: 0.45, weight: "firm", shade: false });
  }
}

export function renderFactionCards(layout, { dpi = 300, seed = 600 } = {}) {
  const [cw, ch] = layout.cards.size_mm;
  const out = [];
  let blank = 0;
  layout.cards.factions.forEach((card, i) => {
    const sheet = new Sheet({ widthMm: cw + BLEED * 2, heightMm: ch + BLEED * 2, dpi, seed: seed + i * 13 });
    const a = new Artist(sheet, { seed: 31 + i });
    const cx = BLEED + cw / 2;
    cardFrame(a, cw, ch);
    text(a, card.name, cx, BLEED + 11, 4.2, { style: "inscribed", medium: "charcoal", track: 0.05 });
    a.line([BLEED + 8, BLEED + 15], [BLEED + cw - 8, BLEED + 15], w("fine", { bow: 0.1 }));
    const ry = BLEED + 37, r = 16;
    if (card.badge) {
      M.tone(a, (c) => c.arc(cx, ry, r + 2.5, 0, PI * 2), [cx - r - 3, ry - r - 3, 2 * r + 6, 2 * r + 6], 0.14, { angle: PI / 4 });
      K.factionSite(a, cx, ry, FACTION_KIND[card.badge], r);
    } else {
      // An empty street: a plain roundel on bare paving.
      for (let k = -2; k <= 2; k++) {
        a.line([cx - r - 4, ry + k * 5], [cx + r + 4, ry + k * 5], w("hair", { alpha: 0.3, bow: 0.05 }));
      }
      K.streetSpace(a, cx, ry, r * 0.75);
    }
    const plateY0 = BLEED + ch - 17.5, plateY1 = BLEED + ch - 5;
    M.lift(a, (c) => c.rect(BLEED + 6, plateY0, cw - 12, plateY1 - plateY0), 0.95);
    a.rect(BLEED + 6, plateY0, cw - 12, plateY1 - plateY0, w("hair", { overshoot: 0.3 }));
    const cap = 2.1;
    card.lines.forEach((ln, k) => text(a, ln.toUpperCase(), cx, plateY0 + 5 + k * cap * 1.9, cap, { medium: "graphite", weight: 1.05 }));
    a.cutRect(BLEED, BLEED, cw, ch);
    const canvas = sheet.compose();
    sheet.release();
    const name = card.badge ? `faction-${FACTION_KIND[card.badge]}.png` : `faction-empty-${++blank}.png`;
    out.push([name, canvas]);
  });
  return out;
}

export function renderFactionBack(layout, { dpi = 300, seed = 660 } = {}) {
  const [cw, ch] = layout.cards.size_mm;
  const sheet = new Sheet({ widthMm: cw + BLEED * 2, heightMm: ch + BLEED * 2, dpi, seed });
  const a = new Artist(sheet, { seed: 41 });
  const cx = BLEED + cw / 2, cy = BLEED + ch / 2;
  cardFrame(a, cw, ch);
  M.tone(a, (c) => c.rect(BLEED + 6, BLEED + 6, cw - 12, ch - 12), [BLEED + 6, BLEED + 6, cw - 12, ch - 12], 0.12, { angle: -PI / 4 });
  M.lift(a, (c) => c.arc(cx, cy - 7, 15.5, 0, PI * 2), 1);
  M.coin(a, cx, cy - 7, 15, { beads: true, worn: 0.08 });
  text(a, "?", cx, cy + 2.5, 18, { style: "inscribed", medium: "charcoal" });
  const devices = [["army", -14], ["officials", 0], ["elites", 14]];
  for (const [kind, dx] of devices) K.factionEmblem(a, cx + dx, cy + 18, 3.4, kind);
  text(a, "FACTION CARD", cx, cy + 29, 2.4, { medium: "charcoal", weight: 1.1, track: 0.1 });
  a.cutRect(BLEED, BLEED, cw, ch);
  const canvas = sheet.compose();
  sheet.release();
  return canvas;
}
