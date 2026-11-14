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
  const u = h / 28;                    // one part
  const top = cy - h / 2;
  groundShadow(a, cx, top + h + 1.2, 6 * u);
  // Blade: the pugio's waisted leaf - broad at the hilt, pinched in the
  // middle, swelling again before a sharp point.
  const tip = [cx, top];
  const bl = (s) => spline([tip, [cx + s * 2.2 * u, top + 3.5 * u], [cx + s * 3.1 * u, top + 6.5 * u],
    [cx + s * 2.3 * u, top + 10 * u], [cx + s * 2.8 * u, top + 13.5 * u], [cx + s * 3.6 * u, top + 15.6 * u]], 7);
  const right = bl(1), left = bl(-1);
  tone(a, poly([...right, [cx, top + 15.6 * u]]), bbox(right, 0.5), 0.5, { angle: PI / 2.2 });
  a.stroke(right, w("firm"));
  a.stroke(left, w("firm"));
  // Raised midrib, drawn double, with a highlight on the lit side.
  a.line([cx - 0.35 * u, top + 1.5 * u], [cx - 0.45 * u, top + 15.4 * u], w("fine", { bow: 0 }));
  a.line([cx + 0.35 * u, top + 1.5 * u], [cx + 0.45 * u, top + 15.4 * u], w("fine", { bow: 0 }));
  a.line([cx - 1.4 * u, top + 4 * u], [cx - 1.2 * u, top + 12 * u], w("hair", { alpha: 0.3, bow: 0 }));
  // Crossguard: a broad tapered bar with rivets at the ends.
  const gy = top + 15.6 * u;
  const guard = [[cx - 5.2 * u, gy], [cx + 5.2 * u, gy], [cx + 4.4 * u, gy + 1.9 * u], [cx - 4.4 * u, gy + 1.9 * u]];
  tone(a, poly(guard), bbox(guard, 0.3), 0.45, { angle: PI / 2 });
  a.polygon(guard, w("bold", { width: 0.5, overshoot: 0.1 }));
  for (const s of [-1, 1]) a.circle(cx + s * 3.6 * u, gy + 0.95 * u, 0.45 * u, w("fine"));
  // Grip: narrow at both ends with a disc node at the middle.
  const g0 = gy + 1.9 * u, g1 = g0 + 6.4 * u, mid = (g0 + g1) / 2;
  const grip = (s) => spline([[cx + s * 1.3 * u, g0], [cx + s * 1.0 * u, mid - 1.4 * u], [cx + s * 1.0 * u, mid + 1.4 * u], [cx + s * 1.4 * u, g1]], 6);
  const gripPts = [...grip(1), ...grip(-1).reverse()];
  tone(a, poly(gripPts), bbox(gripPts, 0.3), 0.35, { angle: PI / 2 });
  a.stroke([...gripPts, gripPts[0]], w("firm"));
  a.ellipse(cx, mid, 2.3 * u, 0.8 * u, w("firm"));
  tone(a, (c) => c.ellipse(cx, mid, 2.3 * u, 0.8 * u, 0, 0, PI * 2), [cx - 2.3 * u, mid - u, 4.6 * u, 2 * u], 0.3, { angle: PI / 2 });
  // Pommel: a wide lens, flat on top, with three rivet heads.
  const py = g1;
  const pom = [...arcPoints(cx, py + 0.9 * u, 4.2 * u, 0.9 * u, PI, 2 * PI, 10),
    ...arcPoints(cx, py + 0.9 * u, 4.2 * u, 1.9 * u, 0, PI, 14).slice(1, -1)];
  tone(a, poly(pom), bbox(pom, 0.3), 0.4, { angle: PI / 2.3 });
  a.stroke([...pom, pom[0]], w("bold", { width: 0.5 }));
  for (const dx of [-2.2, 0, 2.2]) a.circle(cx + dx * u, py + (dx === 0 ? 1.3 : 1.1) * u, 0.4 * u, w("fine"));
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
  // Small pyramidal head.
  const hb = top + 2.6 * u;
  const head = [[cx, top], [cx + 0.95 * u, hb - 0.6 * u], [cx + 0.5 * u, hb], [cx - 0.5 * u, hb], [cx - 0.95 * u, hb - 0.6 * u]];
  tone(a, poly([head[0], head[1], head[2], [cx, hb]]), bbox(head, 0.4), 0.55, { angle: PI / 2.4 });
  a.polygon(head, w("firm", { overshoot: 0.05 }));
  a.line([cx, top + 0.5 * u], [cx, hb], w("hair", { bow: 0 }));
  // The long thin iron shank - the pilum's signature - drawn double.
  const jb = top + 12 * u;
  a.line([cx - 0.28 * u, hb], [cx - 0.32 * u, jb], w("firm", { bow: 0 }));
  a.line([cx + 0.28 * u, hb], [cx + 0.32 * u, jb], w("firm", { bow: 0 }));
  // Wooden block where the shank is riveted into the shaft.
  const blk = [cx - 1.5 * u, jb, 3 * u, 2.8 * u];
  tone(a, (c) => c.rect(...blk), blk, 0.4, { angle: PI / 2 });
  a.rect(...blk, w("bold", { width: 0.45, overshoot: 0.1 }));
  a.line([cx - 1.5 * u, jb + 0.7 * u], [cx + 1.5 * u, jb + 0.7 * u], w("hair", { bow: 0 }));
  for (const s of [-1, 1]) a.circle(cx + s * 0.75 * u, jb + 1.7 * u, 0.3 * u, w("fine"));
  // The wooden shaft: heavier, tapering, with grain.
  const s0 = jb + 2.8 * u, s1 = top + 28.6 * u;
  const shaft = [[cx - 0.95 * u, s0], [cx + 0.95 * u, s0], [cx + 0.75 * u, s1], [cx - 0.75 * u, s1]];
  tone(a, poly([[cx + 0.1 * u, s0], [cx + 0.95 * u, s0], [cx + 0.75 * u, s1], [cx + 0.1 * u, s1]]), bbox(shaft, 0.3), 0.4, { angle: PI / 2.2 });
  a.line(shaft[0], shaft[3], w("firm", { bow: 0 }));
  a.line(shaft[1], shaft[2], w("firm", { bow: 0 }));
  for (let i = 0; i < 4; i++) {
    const y = s0 + (2 + i * 3.4) * u;
    a.line([cx - 0.2 * u, y], [cx - 0.1 * u, y + 2.2 * u], w("hair", { alpha: 0.35, bow: 0 }));
  }
  // Leather grip binding and a short butt spike.
  const gb = s0 + 6 * u;
  for (let i = 0; i < 5; i++) a.line([cx - 0.95 * u, gb + i * 0.5 * u], [cx + 0.95 * u, gb + i * 0.5 * u + 0.3 * u], w("fine", { bow: 0 }));
  a.polygon([[cx - 0.75 * u, s1], [cx + 0.75 * u, s1], [cx, top + 30 * u]], w("firm", { overshoot: 0.05 }));
}

export function galea(a, cx, cy, h) {
  // An Imperial Gallic helmet in side view, facing right: crest, bowl,
  // brow peak, ear cut-out, hanging cheek guard, and a broad flared
  // neck guard at the back.
  const u = h / 26;
  const top = cy - h / 2 + 1.5 * u;
  const ox = cx + 1.2 * u;
  const P = (x, y) => [ox + x * u, top + y * u];
  const Ps = (pts) => pts.map(([x, y]) => P(x, y));
  groundShadow(a, ox - 1 * u, top + 22.6 * u, 8 * u);

  // Neck guard first, so the bowl overlaps it.
  const neck = Ps([[-0.5, 14.4], [-3.2, 14.6], [-6.9, 13.9], [-9.4, 15.6], [-9.8, 16.8], [-6.6, 16.8], [-3.0, 16.0], [-0.6, 15.4]]);
  tone(a, poly(neck), bbox(neck, 0.4), 0.45, { angle: PI / 2.3 });
  a.polygon(neck, w("firm", { overshoot: 0.1 }));
  a.stroke(spline(Ps([[-1.2, 15.2], [-6.4, 15.4], [-9.4, 16.4]]), 6), w("hair", { bow: 0 }));

  // Bowl.
  const bowl = spline(Ps([[-6.9, 14.0], [-7.4, 10.4], [-5.6, 6.8], [-2.0, 5.3], [2.2, 5.3], [5.6, 6.8], [7.3, 10.0], [7.5, 13.2]]), 8);
  const rim = Ps([[7.5, 13.2], [3.7, 14.2]]);
  const ear = arcPoints(ox + 2.2 * u, top + 14.2 * u, 1.5 * u, 1.6 * u, 0, -PI, 12);
  const back = Ps([[0.7, 14.2], [-3.2, 14.6], [-6.9, 14.0]]);
  const outline = [...bowl, ...rim, ...ear, ...back];
  tone(a, poly(outline), bbox(outline, 0.5), 0.18, { angle: PI / 2.6 });
  // Shadow side: the back and underside of the bowl.
  const shade = spline(Ps([[-1.0, 5.5], [-5.6, 6.8], [-7.4, 10.4], [-6.9, 14.0], [-3.2, 14.6], [-2.2, 11.0]]), 7);
  tone(a, poly(shade), bbox(shade, 0.5), 0.5, { angle: PI / 2.3 });
  a.stroke(bowl, w("bold", { width: 0.5 }));
  a.stroke(rim, w("firm", { bow: 0 }));
  a.stroke(ear, w("firm"));
  a.stroke(back, w("firm"));
  // Reinforcing ridge over the crown and embossed brow scrolls.
  a.stroke(spline(Ps([[6.2, 9.4], [4.6, 7.4], [1.0, 6.4], [-3.4, 6.9], [-6.0, 9.2]]), 7), w("hair", { bow: 0 }));
  a.stroke(spline(Ps([[6.6, 11.0], [5.0, 9.7], [3.4, 10.3], [3.9, 11.2]]), 6), w("fine"));
  // Brow peak, a narrow projecting band (not a cap brim).
  const peak = Ps([[7.3, 12.2], [9.2, 11.9], [9.0, 12.8], [7.5, 13.2]]);
  tone(a, poly(peak), bbox(peak, 0.3), 0.5, { angle: PI / 2 });
  a.polygon(peak, w("firm", { overshoot: 0.05 }));

  // Cheek guard hanging from a hinge in front of the ear.
  const cheek = spline(Ps([[3.4, 14.0], [7.4, 13.3], [7.8, 16.6], [6.6, 19.8], [4.6, 20.8], [3.2, 18.6], [2.9, 16.0]]), 7, true);
  tone(a, poly(cheek), bbox(cheek, 0.5), 0.35, { angle: PI / 2.3 });
  a.stroke(cheek, w("firm"));
  // Hinge straps tie the guard to the rim.
  for (const x of [4.2, 6.2]) a.rect(ox + x * u, top + 12.9 * u, 1.0 * u, 1.6 * u, w("fine", { overshoot: 0.05 }));
  a.stroke(spline(Ps([[3.6, 15.0], [7.0, 14.5], [7.2, 16.8], [6.2, 19.2], [4.6, 19.8]]), 6), w("hair", { alpha: 0.5 }));
  for (const [x, y] of [[4.6, 16.4], [6.2, 16.4], [5.2, 18.6]]) a.circle(...P(x, y), 0.35 * u, w("fine"));

  // Crest: a crest-holder on the crown and a sweep of horsehair.
  a.rect(ox - 0.5 * u, top + 4.2 * u, 1.0 * u, 1.2 * u, w("fine", { overshoot: 0.05 }));
  const inner = spline(Ps([[5.4, 6.4], [2.6, 4.9], [0, 4.4], [-3.4, 4.9], [-6.4, 6.6], [-8.0, 9.0]]), 10);
  const outer = spline(Ps([[6.0, 5.8], [4.0, 1.4], [0, -0.2], [-4.4, 0.9], [-7.8, 4.6], [-9.0, 8.8]]), 10);
  const crest = [...inner, ...outer.slice().reverse()];
  tone(a, poly(crest), bbox(crest, 0.5), 0.35, { angle: -PI / 3 });
  const n = 46;
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const pi = inner[Math.round(t * (inner.length - 1))], po = outer[Math.round(t * (outer.length - 1))];
    const j = (a.rng() - 0.5) * 0.6 * u;
    a.line([pi[0] + j, pi[1]], [po[0] + j * 1.5, po[1] + (a.rng() - 0.5) * 0.5 * u], w("hair", { alpha: 0.6, bow: 0.15 }));
  }
  a.stroke(outer, w("fine", { breaks: 0.2 }));
}

export function scutum(a, cx, cy, h) {
  // The legionary's curved rectangular shield, seen from the front and
  // a little above: top and bottom edges bow, tone rolls round the curve.
  const u = h / 30;
  const wd = 20 * u, ht = 27.5 * u, sag = 1.7 * u;
  const top = cy - h / 2 + 0.6 * u;
  const x0 = cx - wd / 2, x1 = cx + wd / 2;
  const edgeY = (x, base) => base + sag * (1 - ((x - cx) / (wd / 2)) ** 2);
  groundShadow(a, cx, top + ht + sag + 1.0, wd * 0.6);
  const N = 16;
  const strip = (fa, fb) => {
    const xa = x0 + fa * wd, xb = x0 + fb * wd, pts = [];
    for (let i = 0; i <= N; i++) { const x = xa + (xb - xa) * (i / N); pts.push([x, edgeY(x, top)]); }
    for (let i = N; i >= 0; i--) { const x = xa + (xb - xa) * (i / N); pts.push([x, edgeY(x, top + ht)]); }
    return pts;
  };
  const face = strip(0, 1);
  // Tone rolls round the curve: light at the left, dark at the right.
  tone(a, poly(strip(0, 0.08)), bbox(strip(0, 0.08), 0.3), 0.25, { angle: PI / 2 });
  tone(a, poly(strip(0.58, 0.78)), bbox(strip(0.58, 0.78), 0.3), 0.3, { angle: PI / 2 });
  tone(a, poly(strip(0.78, 1)), bbox(strip(0.78, 1), 0.3), 0.6, { angle: PI / 2 });
  a.stroke([...face, face[0]], w("bold"));
  // Thickness along the bottom edge.
  const lip = [];
  for (let i = 0; i <= N; i++) { const x = x0 + wd * (i / N); lip.push([x, edgeY(x, top + ht) + 0.8 * u]); }
  a.stroke(lip, w("fine"));
  // Inner rim following the same curve.
  const ri = 1.3 * u, rim = [];
  for (let i = 0; i <= N; i++) { const x = x0 + ri + (wd - 2 * ri) * (i / N); rim.push([x, edgeY(x, top) + ri]); }
  for (let i = N; i >= 0; i--) { const x = x0 + ri + (wd - 2 * ri) * (i / N); rim.push([x, edgeY(x, top + ht) - ri]); }
  a.stroke([...rim, rim[0]], w("fine"));
  // Spine above and below the boss.
  const my = top + ht / 2 + sag;
  for (const [ya, yb] of [[edgeY(cx, top) + ri, my - 4.2 * u], [my + 4.2 * u, edgeY(cx, top + ht) - ri]]) {
    a.line([cx - 0.5 * u, ya], [cx - 0.5 * u, yb], w("fine", { bow: 0 }));
    a.line([cx + 0.5 * u, ya], [cx + 0.5 * u, yb], w("fine", { bow: 0 }));
  }
  // Thunderbolts on the diagonals: zigzags ending in arrow points.
  for (const [sx, sy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
    const p = (t, k) => [cx + sx * (4.2 + t * 4.2) * u + k * sy * 0.7 * u, my + sy * (4.2 + t * 7.4) * u - k * sx * 0.4 * u];
    const zig = [p(0, 0), p(0.33, 1), p(0.5, -1), p(0.85, 0.6)];
    a.stroke(zig, w("firm", { bow: 0 }));
    const end = zig[zig.length - 1];
    a.line(end, [end[0] - sx * 1.0 * u, end[1] - sy * 0.2 * u], w("firm", { bow: 0 }));
    a.line(end, [end[0] - sx * 0.1 * u, end[1] - sy * 1.2 * u], w("firm", { bow: 0 }));
  }
  // Boss: a square iron plate with corner rivets, the round umbo on it.
  const bs = 3.8 * u;
  tone(a, (c) => c.rect(cx - bs, my - bs, bs * 2, bs * 2), [cx - bs, my - bs, bs * 2, bs * 2], 0.2, { angle: PI / 3 });
  a.rect(cx - bs, my - bs, bs * 2, bs * 2, w("firm", { overshoot: 0.1 }));
  for (const [dx, dy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) a.circle(cx + dx * (bs - 0.8 * u), my + dy * (bs - 0.8 * u), 0.35 * u, w("fine"));
  M_lift(a, cx, my, 2.7 * u);
  tone(a, (c) => { c.moveTo(cx, my - 2.6 * u); c.arc(cx, my, 2.6 * u, -PI / 2, PI / 2); c.closePath(); },
    [cx - 3 * u, my - 3 * u, 6 * u, 6 * u], 0.55, { angle: PI / 2 });
  a.circle(cx, my, 2.7 * u, w("bold"));
  a.circle(cx - 0.8 * u, my - 0.8 * u, 0.6 * u, w("hair", { alpha: 0.4 }));
}

function M_lift(a, x, y, r) {
  a.erase((c) => c.arc(x, y, r, 0, PI * 2), { strength: 0.9, blur: 0.3 });
}

export function lorica(a, cx, cy, h) {
  // A segmented cuirass from the front: neck opening, overlapping
  // shoulder plates, breastplates, and the girdle hoops round the trunk.
  const u = h / 30;
  const top = cy - h / 2 + 0.6 * u;
  const P = (x, y) => [cx + x * u, top + y * u];
  const Ps = (pts) => pts.map(([x, y]) => P(x, y));
  groundShadow(a, cx, top + 28.6 * u, 8 * u);
  const sil = spline(Ps([[2.8, 2.2], [6.6, 2.4], [9.2, 4.6], [9.4, 7.0], [7.0, 9.6], [6.4, 12.5], [6.0, 16], [6.6, 20], [6.4, 23.2],
    [0, 23.8], [-6.4, 23.2], [-6.6, 20], [-6.0, 16], [-6.4, 12.5], [-7.0, 9.6], [-9.4, 7.0], [-9.2, 4.6], [-6.6, 2.4], [-2.8, 2.2],
    [-2.0, 3.9], [0, 4.6], [2.0, 3.9]]), 6, true);
  tone(a, poly(sil), bbox(sil, 0.5), 0.15, { angle: PI / 2.8 });
  const side = spline(Ps([[2.6, 4.6], [7.6, 3.0], [9.4, 7.0], [7.0, 9.6], [6.4, 12.5], [6.0, 16], [6.6, 20], [6.4, 23.2], [2.6, 23.6], [3.2, 14]]), 6, true);
  tone(a, poly(side), bbox(side, 0.5), 0.4, { angle: PI / 2.3 });
  a.stroke(sil, w("bold", { width: 0.5 }));
  // Shoulder plates: bands parallel to each shoulder line.
  for (const s of [-1, 1]) {
    for (let i = 1; i <= 3; i++) {
      const pts = spline(Ps([[s * (2.9 + i * 0.3), 2.2 + i * 1.2], [s * (6.4 - i * 0.2), 2.4 + i * 1.25], [s * (9.0 - i * 0.6), 4.8 + i * 1.15]]), 6);
      a.stroke(pts, w("firm", { bow: 0 }));
    }
  }
  // Breastplates: a centre seam and a lower edge with rivets.
  a.line(P(0, 4.6), P(0, 10.6), w("fine", { bow: 0 }));
  const bp = spline(Ps([[-6.8, 9.8], [0, 10.8], [6.8, 9.8]]), 8);
  a.stroke(bp, w("firm"));
  for (const x of [-4.6, -2.2, 2.2, 4.6]) a.circle(...P(x, 9.6 + (Math.abs(x) < 3 ? 0.4 : 0)), 0.28 * u, w("hair"));
  // Girdle hoops, every other one in shadow, closed at the front.
  const hw = (y) => (y < 16 ? 6.4 - (y - 12.5) * 0.11 : 6.0 + (y - 16) * 0.15);
  for (let i = 0; i < 5; i++) {
    const y = 12.6 + i * 2.25, x = hw(y);
    const band = spline(Ps([[-x, y - 0.8], [0, y], [x, y - 0.8]]), 8);
    a.stroke(band, w("firm", { bow: 0 }));
    if (i % 2 === 1) {
      const nxt = spline(Ps([[x, y + 1.45], [0, y + 2.25], [-x, y + 1.45]]), 8);
      tone(a, poly([...band, ...nxt]), bbox(band.concat(nxt), 0.3), 0.25, { angle: PI / 2.4 });
    }
    a.circle(...P(0, y + 1.0), 0.3 * u, w("hair"));
  }
  a.line(P(0, 10.8), P(0, 23.8), w("fine", { bow: 0 }));
  // Hanging straps below the hem.
  for (const s of [-1, -0.33, 0.33, 1]) {
    const x0 = s * 4.0;
    a.stroke(spline(Ps([[x0, 23.5], [x0 + s * 0.4, 25.8], [x0 + s * 0.3, 27.6]]), 6), w("fine"));
    a.circle(...P(x0 + s * 0.3, 28.0), 0.45 * u, w("fine"));
  }
}

export const DEVICES = { dagger: pugio, pilum, helmet: galea, scutum, gladius, armor: lorica };
