// The six pieces of equipment, drawn from life like museum catalogue
// plates: a dagger, a javelin, a helmet, a shield, a sword, a cuirass.
// Each device draws centred at (cx, cy) with height h. Light from the
// upper left; forms are built from contour plus form-following hatching,
// and each object rests on a soft shadow.
import { arcPoints, spline } from "./brush.mjs";
import { W, poly, bbox, tone } from "./motifs.mjs";

const PI = Math.PI;
const w = (name, extra = {}) => ({ ...W[name], ...extra });

function groundShadow(a, cx, cy, r) {
  a.smudge((c) => c.ellipse(cx + r * 0.25, cy + r * 0.18, r, r * 0.28, 0, 0, PI * 2), { alpha: 0.3, blur: 1.4 });
  // A few darker flicks under the object, like dust.
  for (let i = 0; i < 9; i++) {
    const x = cx + (a.rng() * 2 - 1) * r * 0.9;
    a.line([x, cy + a.rng() * 1.2], [x + (a.rng() - 0.3) * 2.2, cy + a.rng() * 1.4], w("hair", { alpha: 0.3, bow: 0.2 }));
  }
}

export function pugio(a, cx, cy, h) {
  const u = h / 26;                    // one part
  const top = cy - h / 2;
  groundShadow(a, cx, top + h + 1.2, 6 * u);
  // Blade: a leaf shape, widest two thirds up.
  const tip = [cx, top];
  const bl = (s) => spline([tip, [cx + s * 3.6 * u, top + 5 * u], [cx + s * 4.1 * u, top + 8.5 * u], [cx + s * 2.6 * u, top + 13.5 * u], [cx, top + 14.5 * u]], 7);
  const right = bl(1), left = bl(-1);
  tone(a, poly(right), bbox(right, 0.5), 0.5, { angle: PI / 2.2 });
  tone(a, poly([...left.slice().reverse(), [cx + 1.2 * u, top + 8 * u]]), bbox(left, 0.5), 0.22, { angle: PI / 2.2 });
  a.stroke(right, w("firm"));
  a.stroke(left, w("firm"));
  // Midrib and a caught highlight.
  a.line([cx, top + 1.5 * u], [cx, top + 13.8 * u], w("firm", { bow: 0 }));
  a.line([cx + 1.4 * u, top + 3 * u], [cx + 1.6 * u, top + 11 * u], w("hair", { alpha: 0.3, bow: 0 }));
  // Guard, grip with rivets, pommel.
  const gy = top + 14.5 * u;
  a.rect(cx - 3.7 * u, gy, 7.4 * u, 1.1 * u, w("firm", { overshoot: 0.15 }));
  tone(a, (c) => c.rect(cx - 3.4 * u, gy + 1.1 * u, 6.8 * u, 5.6 * u), [cx - 3.4 * u, gy + 1.1 * u, 6.8 * u, 5.6 * u], 0.35, { angle: PI / 2 });
  for (let i = 0; i < 3; i++) a.circle(cx, gy + (2.2 + i * 1.5) * u, 0.5 * u, w("fine"));
  a.stroke(spline([[cx - 2.1 * u, gy + 1.1 * u], [cx - 2.4 * u, gy + 3.9 * u], [cx - 2.1 * u, gy + 6.7 * u]], 6), w("firm", { bow: 0 }));
  a.stroke(spline([[cx + 2.1 * u, gy + 1.1 * u], [cx + 2.4 * u, gy + 3.9 * u], [cx + 2.1 * u, gy + 6.7 * u]], 6), w("firm", { bow: 0 }));
  a.ellipse(cx, gy + 8.1 * u, 2.2 * u, 1.8 * u, w("firm"));
  a.circle(cx, gy + 8.1 * u, 0.5 * u, w("hair"));
}

export function gladius(a, cx, cy, h) {
  const u = h / 30;
  const top = cy - h / 2;
  groundShadow(a, cx, top + h + 1.2, 6.5 * u);
  // Blade: parallel edges, a long point.
  const tip = [cx, top];
  const edge = (s) => spline([tip, [cx + s * 2.6 * u, top + 8 * u], [cx + s * 2.9 * u, top + 17 * u], [cx + s * 2.9 * u, top + 19 * u]], 7);
  const right = edge(1), left = edge(-1);
  tone(a, poly(right), bbox(right, 0.5), 0.45, { angle: PI / 2.1 });
  a.stroke(right, w("firm"));
  a.stroke(left, w("firm"));
  a.line([cx, top + 2 * u], [cx, top + 18.4 * u], w("firm", { bow: 0 }));
  a.line([cx + 1.3 * u, top + 5 * u], [cx + 1.45 * u, top + 16 * u], w("hair", { alpha: 0.35, bow: 0 }));
  // Guard boss, grip with cord rings, disc pommel.
  const gy = top + 19 * u;
  a.ellipse(cx, gy + 0.8 * u, 3.4 * u, 1.2 * u, w("firm"));
  a.rect(cx - 1.7 * u, gy + 1.8 * u, 3.4 * u, 6 * u, w("firm", { overshoot: 0.12 }));
  tone(a, (c) => c.rect(cx - 1.5 * u, gy + 1.9 * u, 3 * u, 5.8 * u), [cx - 1.5 * u, gy + 1.9 * u, 3 * u, 5.8 * u], 0.3, { angle: PI / 2 });
  for (let i = 0; i < 4; i++) a.line([cx - 1.6 * u, gy + (2.8 + i * 1.2) * u], [cx + 1.6 * u, gy + (2.8 + i * 1.2) * u], w("hair", { bow: 0 }));
  a.ellipse(cx, gy + 9 * u, 2.6 * u, 2.2 * u, w("firm"));
  tone(a, (c) => c.ellipse(cx + 0.8 * u, gy + 9 * u, 1.6 * u, 1.7 * u, 0, 0, PI * 2), [cx - 1 * u, gy + 7 * u, 3 * u, 4 * u], 0.4, { angle: PI / 2 });
  a.circle(cx, gy + 9 * u, 0.4 * u, w("hair"));
}

export function pilum(a, cx, cy, h) {
  const u = h / 30;
  const top = cy - h / 2;
  groundShadow(a, cx, top + h + 1.2, 5 * u);
  // Shaft with a slight sag, head at the top.
  const shaft = spline([[cx - 0.6 * u, top + 7 * u], [cx + 0.3 * u, top + 16 * u], [cx, top + 27 * u]], 8);
  a.stroke(shaft, w("firm", { bow: 0 }));
  a.stroke(shaft.map(([x, y]) => [x + 1.1 * u, y + 0.25 * u]), w("hair", { alpha: 0.4, bow: 0 }));
  for (let i = 0; i < 5; i++) {
    const t = (i + 0.5) / 5, y = top + (9 + t * 15) * u;
    a.line([cx - 0.6 * u + 0.9 * u * t, y], [cx + 0.6 * u + 0.9 * u * t, y], w("hair", { alpha: 0.35, bow: 0 }));
  }
  // Pyramidal head: a long diamond with centre edges.
  const hy = top + 6.6 * u;
  const head = [[cx, top], [cx + 1.3 * u, top + 2.4 * u], [cx + 0.8 * u, hy], [cx, top + 7.2 * u], [cx - 0.8 * u, hy], [cx - 1.3 * u, top + 2.4 * u]];
  tone(a, poly([head[0], head[1], head[2], head[3]]), bbox(head, 0.5), 0.5, { angle: PI / 2.4 });
  a.polygon(head, w("firm", { overshoot: 0.06 }));
  a.line([cx, top + 0.8 * u], [cx, top + 6.8 * u], w("hair", { bow: 0 }));
  // Collar and lead weight at the butt.
  a.rect(cx - 1.5 * u, top + 6.8 * u, 3 * u, 0.9 * u, w("firm", { overshoot: 0.08 }));
  const wy = top + 27.6 * u;
  a.ellipse(cx, wy, 1.7 * u, 1.5 * u, w("firm"));
  tone(a, (c) => c.ellipse(cx + 0.5 * u, wy, 1 * u, 1.2 * u, 0, 0, PI * 2), [cx - 1.7 * u, wy - 1.5 * u, 3.4 * u, 3 * u], 0.45, { angle: PI / 2 });
}

export function galea(a, cx, cy, h) {
  const u = h / 24;
  const top = cy - h / 2;
  groundShadow(a, cx + 1 * u, top + h + 0.6, 7 * u);
  // Dome: a high arch from brow to nape.
  const dome = spline([[cx - 6 * u, top + 10 * u], [cx - 6 * u, top + 6 * u], [cx - 3.5 * u, top + 1.6 * u],
    [cx, top + 0.4 * u], [cx + 3.5 * u, top + 1.4 * u], [cx + 6.4 * u, top + 6 * u], [cx + 6.6 * u, top + 11 * u]], 10);
  const domeShade = spline([[cx + 1 * u, top + 0.6 * u], [cx + 4 * u, top + 1.8 * u], [cx + 6.3 * u, top + 6 * u], [cx + 6.5 * u, top + 11 * u],
    [cx + 4 * u, top + 10.6 * u], [cx + 1.4 * u, top + 6 * u]], 8);
  tone(a, poly(domeShade), bbox(domeShade, 0.5), 0.5, { angle: 0.35 });
  a.stroke(dome, w("firm"));
  // Brim forward (right), neck guard back.
  a.stroke(spline([[cx + 6 * u, top + 9.4 * u], [cx + 9.6 * u, top + 10.6 * u], [cx + 10 * u, top + 11.8 * u], [cx + 6.6 * u, top + 11.4 * u]], 7), w("firm"));
  a.stroke(spline([[cx - 6 * u, top + 9.6 * u], [cx - 6.4 * u, top + 11.8 * u], [cx - 3.4 * u, top + 13.2 * u], [cx - 0.5 * u, top + 13.4 * u]], 7), w("firm"));
  tone(a, poly([[cx - 6.1 * u, top + 10 * u], [cx - 6.4 * u, top + 11.8 * u], [cx - 3.4 * u, top + 13.2 * u], [cx - 0.5 * u, top + 13.4 * u], [cx - 0.5 * u, top + 12.4 * u], [cx - 3 * u, top + 12 * u]]), bbox([[-7 * u + cx, 9 * u + top], [cx + 1 * u, top + 14 * u]], 1), 0.4, { angle: PI / 2.4 });
  // Cheek guard hanging at the front, with rivet holes.
  const cheek = spline([[cx + 6.2 * u, top + 11.6 * u], [cx + 6.7 * u, top + 15 * u], [cx + 5.4 * u, top + 18.4 * u],
    [cx + 3.4 * u, top + 18.9 * u], [cx + 3 * u, top + 15.6 * u], [cx + 4.4 * u, top + 12.2 * u]], 8);
  tone(a, poly(cheek), bbox(cheek, 0.5), 0.42, { angle: PI / 2.3 });
  a.stroke(cheek, w("firm"));
  for (let i = 0; i < 3; i++) a.circle(cx + (4.1 + i * 0.9) * u, top + (13.6 + i * 1.4) * u, 0.4 * u, w("hair"));
  // Brow ridge and a knob at the crown.
  a.stroke(spline([[cx - 5.6 * u, top + 9.6 * u], [cx, top + 8.2 * u], [cx + 5.9 * u, top + 9.6 * u]], 8), w("firm", { bow: 0.05 }));
  a.circle(cx, top + 0.5 * u, 0.7 * u, w("fine"));
}

export function scutum(a, cx, cy, h) {
  const u = h / 30;
  const top = cy - h / 2;
  const wd = 22 * u, ht = 29 * u;
  groundShadow(a, cx, top + ht + 1.4, wd * 0.6);
  // The shield face, curved: sides bow inward.
  const face = [[cx - wd / 2 + 1.5 * u, top], [cx + wd / 2 - 1.5 * u, top],
    spline([[cx + wd / 2 - 1.5 * u, top], [cx + wd / 2, top + ht / 2], [cx + wd / 2 - 1.5 * u, top + ht]], 5).slice(1, -1),
    [cx + wd / 2 - 1.5 * u, top + ht], [cx - wd / 2 + 1.5 * u, top + ht],
    spline([[cx - wd / 2 + 1.5 * u, top + ht], [cx - wd / 2, top + ht / 2], [cx - wd / 2 + 1.5 * u, top]], 5).slice(1, -1)].flat();
  const facePath = poly(face);
  // Border band and an outer edge zone, shaded darker right and bottom.
  tone(a, facePath, bbox(face, 1), 0.28, { angle: PI / 2.6 });
  tone(a, poly(spline([[cx + wd / 2 - 4.5 * u, top + 3 * u], [cx + wd / 2 - 2.6 * u, top + ht / 2], [cx + wd / 2 - 4.5 * u, top + ht - 3 * u]], 7)),
    bbox(face, 1), 0.35, { angle: PI / 2.2 });
  a.polygon(face, w("bold", { overshoot: 0.2 }));
  // Inner border band following the curve.
  a.stroke(spline([[cx - wd / 2 + 3.4 * u, top + 2.2 * u], [cx - wd / 2 + 2.2 * u, top + ht / 2], [cx - wd / 2 + 3.4 * u, top + ht - 2.2 * u]], 8), w("fine"));
  a.stroke(spline([[cx + wd / 2 - 3.4 * u, top + 2.2 * u], [cx + wd / 2 - 2.2 * u, top + ht / 2], [cx + wd / 2 - 3.4 * u, top + ht - 2.2 * u]], 8), w("fine"));
  a.line([cx - wd / 2 + 3.6 * u, top + 2.1 * u], [cx + wd / 2 - 3.6 * u, top + 2.1 * u], w("fine", { bow: 0.15 }));
  a.line([cx - wd / 2 + 3.6 * u, top + ht - 2.1 * u], [cx + wd / 2 - 3.6 * u, top + ht - 2.1 * u], w("fine", { bow: 0.15 }));
  // Winged thunderbolt: boss and symmetric wings of zigzag strokes.
  a.circle(cx, top + ht / 2, 2.6 * u, w("bold"));
  a.circle(cx, top + ht / 2, 1.1 * u, w("firm"));
  tone(a, (c) => { c.moveTo(cx + 0.4 * u, top + ht / 2 - 2.4 * u); c.arc(cx + 0.4 * u, top + ht / 2, 2.4 * u, -PI / 2, PI / 2); c.closePath(); },
    [cx - 3 * u, top + ht / 2 - 3 * u, 6 * u, 6 * u], 0.5, { angle: PI / 2 });
  const wing = (s) => {
    const pts1 = [[cx + s * 2.8 * u, top + ht / 2 - 0.6 * u], [cx + s * 5.5 * u, top + ht / 2 - 2.6 * u],
      [cx + s * 6.5 * u, top + ht / 2 - 0.2 * u], [cx + s * 5 * u, top + ht / 2 + 1.4 * u]];
    const pts2 = [[cx + s * 3 * u, top + ht / 2 + 1.2 * u], [cx + s * 5 * u, top + ht / 2 + 0.4 * u],
      [cx + s * 6.8 * u, top + ht / 2 + 2.6 * u], [cx + s * 3.6 * u, top + ht / 2 + 4.4 * u]];
    a.stroke(spline(pts1, 7), w("firm", { bow: 0.08 }));
    a.stroke(spline(pts2, 7), w("firm", { bow: 0.08 }));
    tone(a, poly(spline(pts1, 7).concat(spline(pts2, 7).slice().reverse())), bbox(pts1.concat(pts2), 1), 0.3, { angle: 0.4 });
  };
  wing(1); wing(-1);
}

export function lorica(a, cx, cy, h) {
  const u = h / 30;
  const top = cy - h / 2;
  groundShadow(a, cx, top + h + 1.0, 8 * u);
  // Torso silhouette: shoulders, chest, waist flare.
  const torso = spline([[cx - 8.2 * u, top + 6.5 * u], [cx - 6.4 * u, top + 3.2 * u], [cx - 2.6 * u, top + 1.4 * u],
    [cx, top + 1 * u], [cx + 2.6 * u, top + 1.3 * u], [cx + 6.4 * u, top + 3.1 * u], [cx + 8.3 * u, top + 6.6 * u],
    [cx + 7.4 * u, top + 11 * u], [cx + 6 * u, top + 16 * u], [cx + 6.4 * u, top + 20 * u], [cx + 5.2 * u, top + 22.5 * u],
    [cx, top + 23.5 * u], [cx - 5.2 * u, top + 22.5 * u], [cx - 6.4 * u, top + 20 * u], [cx - 6 * u, top + 16 * u],
    [cx - 7.4 * u, top + 11 * u]], 8, false);
  // Breastplates: two chest discs and the collar line.
  tone(a, poly(torso), bbox(torso, 1), 0.3, { angle: PI / 2.8 });
  // Side shading, away from the light.
  tone(a, poly(spline([[cx + 2 * u, top + 1.3 * u], [cx + 6.4 * u, top + 3.1 * u], [cx + 8.3 * u, top + 6.6 * u],
    [cx + 7.4 * u, top + 11 * u], [cx + 6 * u, top + 16 * u], [cx + 6.4 * u, top + 20 * u], [cx + 5.2 * u, top + 22.5 * u],
    [cx, top + 23.5 * u], [cx + 1.4 * u, top + 20 * u], [cx + 2.4 * u, top + 12 * u]], 8)), bbox(torso, 1), 0.32, { angle: PI / 2.3 });
  a.stroke(torso, w("firm"));
  // Shoulder guards: layered strips over each shoulder.
  for (const s of [-1, 1]) {
    for (let i = 0; i < 3; i++) {
      const pts = spline([[cx + s * (6.2 - i * 1.9) * u, top + (2.2 + i * 1.7) * u],
        [cx + s * (3.4 - i * 1.1) * u, top + (3.4 + i * 1.9) * u], [cx + s * (2.6 - i * 0.9) * u, top + (6.4 + i * 1.6) * u]], 6);
      a.stroke(pts, w("firm", { bow: 0.04 }));
      if (i === 0) tone(a, poly(pts.concat([[cx + s * 0.6 * u, top + 8 * u]])), bbox(pts, 1), 0.28, { angle: s > 0 ? PI / 2.2 : PI / 2.6 });
    }
  }
  // Girdle plates: horizontal bands across the trunk.
  for (let i = 0; i < 4; i++) {
    const yy = top + (8.5 + i * 2.9) * u;
    const bow = 1.2 * u * (1 - i * 0.15);
    a.stroke(spline([[cx - (6.6 - i * 0.5) * u, yy - 1.4 * u], [cx, yy], [cx + (6.6 - i * 0.5) * u, yy - 1.4 * u]], 7), w("firm", { bow: 0 }));
    const bandPts = spline([[cx - (6.5 - i * 0.5) * u, yy - 1.4 * u], [cx, yy], [cx + (6.5 - i * 0.5) * u, yy - 1.4 * u],
      [cx + (6 - i * 0.5) * u, yy + 0.6 * u], [cx, yy + 2 * u], [cx - (6 - i * 0.5) * u, yy + 0.6 * u]], 7);
    if (i % 2 === 1) tone(a, poly(bandPts), bbox(bandPts, 1), 0.2, { angle: PI / 2.4 });
  }
  // Leather straps and apron ties below the girdle.
  for (const s of [-1, -0.33, 0.33, 1]) {
    const x0 = cx + s * 4.2 * u;
    a.stroke(spline([[x0, top + 20.4 * u], [x0 + s * 0.6 * u, top + 24 * u], [x0 + s * 0.4 * u, top + 27 * u]], 6), w("fine"));
    a.circle(x0 + s * 0.4 * u, top + 27.4 * u, 0.5 * u, w("hair"));
  }
}

export const DEVICES = { dagger: pugio, pilum, helmet: galea, scutum, gladius, armor: lorica };
