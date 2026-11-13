// The play symbols shared by both maps. They are drawn last, on ground
// cleared with the eraser, so a pawn always sits on a clean, legible spot
// whatever the drawing around it does.
import { arcPoints } from "./brush.mjs";
import { text } from "./letters.mjs";
import { W, poly, bbox, tone, star, octagonPts, lift, laurelWreath } from "./motifs.mjs";
import { archway } from "./motifs.mjs";

const PI = Math.PI;
const w = (name, extra = {}) => ({ ...W[name], ...extra });

// A shallow shadow crescent on the lower right of a ring: the roundel is
// a slab set into the paving.
function slabShadow(a, x, y, r, depth) {
  const pts = arcPoints(x, y, r + depth, r + depth, -0.35, PI * 0.85, 24).concat(arcPoints(x, y, r, r, PI * 0.85, -0.35, 24));
  a.hatch(poly(pts), bbox(pts), { angle: -PI / 4, gap: 0.42, ...W.hair, alpha: 0.6, run: 4 });
}

export function streetSpace(a, x, y, r = 9.2) {
  lift(a, (c) => c.arc(x, y, r + 0.5, 0, PI * 2), 1);
  slabShadow(a, x, y, r, Math.max(0.5, r * 0.07));
  a.circle(x, y, r, w("firm", { width: Math.max(0.3, r * 0.05) }));
  // A faint inner ring, broken, like a worn carved edge.
  a.stroke(arcPoints(x, y, r * 0.9, r * 0.9, PI * 0.9, PI * 1.75, 20), w("hair", { alpha: 0.4, breaks: 0.1 }));
}

export function treasureEntry(a, x, y, letter, r = 10.6) {
  lift(a, (c) => c.arc(x, y, r + 0.7, 0, PI * 2), 1);
  slabShadow(a, x, y, r, Math.max(0.6, r * 0.08));
  a.circle(x, y, r, w("bold", { width: Math.max(0.4, r * 0.075), passes: 1 }));
  const ri = r * 0.72;
  a.circle(x, y, ri, w("fine"));
  // Beads between the rings: the treasure entries read like coins.
  const n = Math.max(12, Math.round(r * 2.6));
  for (let i = 0; i < n; i++) {
    const t = (i / n) * PI * 2;
    a.circle(x + Math.cos(t) * (r + ri) / 2, y + Math.sin(t) * (r + ri) / 2, Math.max(0.15, r * 0.045), w("fine"));
  }
  if (letter) text(a, letter, x, y + r * 0.33, r * 0.66, { style: "inscribed", medium: "charcoal" });
}

export function gateMark(a, x, y, r = 11.4) {
  lift(a, (c) => c.arc(x, y, r + 0.7, 0, PI * 2), 1);
  slabShadow(a, x, y, r, Math.max(0.6, r * 0.08));
  a.circle(x, y, r, w("heavy", { width: Math.max(0.5, r * 0.085), passes: 1 }));
  a.circle(x, y, r * 0.88, w("fine"));
  archway(a, x, y + r * 0.5, r * 0.82, r * 1.0, { dark: 0.55, voussoirs: 9 });
  // The threshold.
  a.line([x - r * 0.62, y + r * 0.5], [x + r * 0.62, y + r * 0.5], w("firm", { bow: 0 }));
}

export function peristyle(a, x, y, r = 11.2) {
  lift(a, poly(octagonPts(x, y, r + 0.8)), 1);
  const outer = octagonPts(x, y, r);
  const shadow = outer.map(([px, py]) => [px + 0.8, py + 0.8]);
  a.hatch(poly(shadow), bbox(shadow), { angle: -PI / 4, gap: 0.45, ...W.hair, alpha: 0.5, run: 4 });
  lift(a, poly(outer), 1);
  a.polygon(outer, w("heavy", { width: Math.max(0.5, r * 0.07), overshoot: 0.25 }));
  const inner = octagonPts(x, y, r * 0.73);
  a.polygon(inner, w("fine", { overshoot: 0.2 }));
  // Eight columns stand in the ring between the two octagons.
  for (let i = 0; i < 8; i++) {
    const t = PI / 8 + (i * PI) / 4;
    const cx = x + Math.cos(t) * r * 0.86, cy = y + Math.sin(t) * r * 0.86;
    a.circle(cx, cy, Math.max(0.25, r * 0.06), w("firm"));
  }
  // The crossing: an eight-point mosaic star marks the throne.
  star(a, x, y, r * 0.55, { points: 8, inner: 0.42, weight: "bold" });
}

export function guardPost(a, x, y, r = 9.6) {
  lift(a, (c) => c.arc(x, y, r + 0.6, 0, PI * 2), 1);
  star(a, x, y - r * 0.12, r * 0.86, { points: 8, inner: 0.5, weight: "bold" });
  text(a, "4+", x, y + r * 0.95, r * 0.26, { medium: "charcoal", weight: 1.3 });
}

// Faction meeting places on the succession map.
export function factionSite(a, x, y, kind, r = 7.8) {
  lift(a, (c) => c.arc(x, y, r + 0.7, 0, PI * 2), 1);
  slabShadow(a, x, y, r, Math.max(0.6, r * 0.08));
  a.circle(x, y, r, w("bold", { width: Math.max(0.4, r * 0.07) }));
  a.circle(x, y, r * 0.86, w("hair"));
  factionEmblem(a, x, y, r * 0.62, kind);
}

// The three faction devices: the army's shield, the officials' column,
// the elites' laurel.
export function factionEmblem(a, x, y, s, kind) {
  if (kind === "army") {
    // A legionary scutum seen from the front, with boss and thunderbolt.
    const hw = s * 0.55, hh = s * 0.85;
    const pts = [[x - hw, y - hh * 0.92], [x, y - hh], [x + hw, y - hh * 0.92], [x + hw * 1.04, y], [x + hw, y + hh * 0.92],
      [x, y + hh], [x - hw, y + hh * 0.92], [x - hw * 1.04, y]];
    const side = [[x + hw * 0.55, y - hh * 0.95], [x + hw, y - hh * 0.92], [x + hw * 1.04, y], [x + hw, y + hh * 0.92], [x + hw * 0.55, y + hh * 0.95]];
    tone(a, poly(side), bbox(side), 0.6, { angle: PI / 2 });
    a.polygon(pts, w("firm", { overshoot: 0.1 }));
    a.circle(x, y, s * 0.2, w("firm"));
    a.circle(x, y, s * 0.11, w("fine"));
    for (const d of [-1, 1]) {
      a.stroke([[x, y + d * s * 0.2], [x - s * 0.12, y + d * s * 0.45], [x + s * 0.1, y + d * s * 0.5], [x, y + d * s * 0.78]], w("fine"));
    }
  } else if (kind === "officials") {
    const h = s * 1.7;
    const top = y - h / 2;
    const sw = s * 0.36;
    const shaft = [[x - sw / 2, top + h * 0.14], [x + sw / 2, top + h * 0.14], [x + sw / 2, top + h * 0.86], [x - sw / 2, top + h * 0.86]];
    const shade = [[x + sw * 0.1, shaft[0][1]], shaft[1], shaft[2], [x + sw * 0.1, shaft[2][1]]];
    tone(a, poly(shade), bbox(shade), 0.55, { angle: PI / 2 });
    a.line(shaft[0], shaft[3], w("firm", { bow: 0 }));
    a.line(shaft[1], shaft[2], w("firm", { bow: 0 }));
    for (const f of [-0.25, 0, 0.25]) a.line([x + f * sw, shaft[0][1] + 0.3], [x + f * sw, shaft[2][1] - 0.3], w("hair", { bow: 0 }));
    a.rect(x - sw * 0.85, top, sw * 1.7, h * 0.08, w("firm", { overshoot: 0.1 }));
    a.rect(x - sw * 0.65, top + h * 0.08, sw * 1.3, h * 0.06, w("fine", { overshoot: 0.1 }));
    a.rect(x - sw * 0.85, top + h * 0.92, sw * 1.7, h * 0.08, w("firm", { overshoot: 0.1 }));
    a.rect(x - sw * 0.65, top + h * 0.86, sw * 1.3, h * 0.06, w("fine", { overshoot: 0.1 }));
  } else {
    laurelWreath(a, x, y - s * 0.05, s * 0.78, { pairs: 5, leafLen: s * 0.42, leafWid: s * 0.15, gap: 0.55 });
  }
}

export { tone };
