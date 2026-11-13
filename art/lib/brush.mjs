// Dry-media brushes. Every mark is built from the act of drawing: a stroke
// is a path the hand follows, with pressure that rises and falls, a point
// made of several grains that each leave their own broken trace, and a
// wobble that comes from the arm, not from a filter.
//
// All units are millimetres. Media:
//   graphite - hard, fine, slightly silver; outlines and fine hatching.
//   charcoal - soft, grainy, dark; accents and the heaviest contours.
//   wash     - smudged graphite powder, laid with a stump; soft tone.
//   chalk    - white; lifts tone back out (an eraser or white conte).

// ---------------------------------------------------------------------------
// Path helpers.

export function dist(a, b) { return Math.hypot(b[0] - a[0], b[1] - a[1]); }

// Resample a polyline at a fixed step so pressure and wobble act evenly.
export function resample(points, step) {
  if (points.length < 2) return points.slice();
  const out = [points[0]];
  let carry = 0;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i];
    const d = dist(a, b);
    if (d === 0) continue;
    let t = (step - carry) / d;
    while (t <= 1) {
      out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
      t += step / d;
    }
    carry = (carry + d) % step;
  }
  const last = points[points.length - 1];
  if (dist(out[out.length - 1], last) > step * 0.25) out.push(last);
  return out;
}

// Catmull-Rom through control points: hand paths are smooth curves.
export function spline(points, perSeg = 8, closed = false) {
  const P = closed ? [points[points.length - 1], ...points, points[0], points[1]]
    : [points[0], ...points, points[points.length - 1]];
  const out = [];
  for (let i = 1; i < P.length - 2; i++) {
    const [p0, p1, p2, p3] = [P[i - 1], P[i], P[i + 1], P[i + 2]];
    for (let s = 0; s < perSeg; s++) {
      const t = s / perSeg, t2 = t * t, t3 = t2 * t;
      out.push([0, 1].map((k) => 0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t +
        (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)));
    }
  }
  out.push(closed ? P[P.length - 2] : points[points.length - 1]);
  return out;
}

export function arcPoints(cx, cy, rx, ry, a0, a1, n = 48) {
  const out = [];
  for (let i = 0; i <= n; i++) {
    const a = a0 + (a1 - a0) * (i / n);
    out.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]);
  }
  return out;
}

// ---------------------------------------------------------------------------
// The artist. One Artist per sheet carries the hand's habits: how much it
// wobbles, how hard it presses, and its random state.

export class Artist {
  constructor(sheet, { wobble = 1, seed = 1 } = {}) {
    this.sheet = sheet;
    this.rng = sheet.rng.fork(seed);
    this.noise = sheet.noise;
    this.wobble = wobble;
    this.t = this.rng() * 1000;      // a running "time" for the hand's noise
  }

  // Displace a path by low-frequency noise along its normal: the arm.
  wobblePath(points, amp = 0.25, freq = 0.12) {
    const n = this.noise, base = this.t += 17.3;
    let along = 0;
    return points.map((p, i) => {
      if (i > 0) along += dist(points[i - 1], p);
      const a = points[Math.max(0, i - 1)], b = points[Math.min(points.length - 1, i + 1)];
      const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
      const off = n.n1(base + along * freq) * amp * this.wobble + n.n1(base * 1.7 + along * freq * 4.1) * amp * 0.25 * this.wobble;
      return [p[0] - (dy / len) * off, p[1] + (dx / len) * off];
    });
  }

  // A single stroke. opts:
  //   medium   graphite | charcoal | wash | chalk
  //   width    tip width in mm at full pressure
  //   alpha    pigment load at full pressure
  //   grains   number of strands in the tip (more = smoother)
  //   taper    [in, out] fraction of length spent landing and lifting
  //   pressure optional f(t) -> 0..1 override
  //   wobble   wobble amplitude in mm (0 for a ruled line)
  //   breaks   chance per mm of the tip skipping
  stroke(points, opts = {}) {
    const o = {
      medium: "graphite", width: 0.35, alpha: 0.75, grains: 4, taper: [0.12, 0.2],
      wobble: 0.18, freq: 0.12, breaks: 0.0, pressure: null, step: null, ...opts,
    };
    const ctx = this.sheet.ctx(o.medium);
    const rng = this.rng, n = this.noise;
    const step = o.step || Math.max(0.12, Math.min(0.6, o.width * 0.55));
    let path = resample(points, step);
    if (path.length < 2) return;
    if (o.wobble) path = this.wobblePath(path, o.wobble, o.freq);
    const total = path.length - 1;
    const color = o.medium === "chalk" ? "#fff" : "#000";
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineCap = "butt";
    // Each grain is a strand offset across the tip, with its own skips.
    const base = this.t += 31.7;
    for (let g = 0; g < o.grains; g++) {
      const across = o.grains === 1 ? 0 : (g / (o.grains - 1) - 0.5);
      const gw = o.width / Math.max(1, o.grains * 0.5);
      const gSeed = base + g * 13.1;
      let skipping = false;
      for (let i = 1; i < path.length; i++) {
        const t = i / total;
        const land = o.taper[0] > 0 ? Math.min(1, t / o.taper[0]) : 1;
        const lift = o.taper[1] > 0 ? Math.min(1, (1 - t) / o.taper[1]) : 1;
        let p = o.pressure ? o.pressure(t) : Math.sqrt(land) * Math.sqrt(lift);
        p *= 0.82 + 0.18 * n.n1(gSeed + i * 0.08);
        if (o.breaks) {
          if (skipping) { if (rng() < 0.35) skipping = false; continue; }
          if (rng() < o.breaks * step) { skipping = true; continue; }
        }
        const a = path[i - 1], b = path[i];
        const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
        const nx = -dy / len, ny = dx / len;
        // Strand position wanders a little across the tip.
        const off = (across * 0.7 + n.n1(gSeed * 0.7 + i * 0.05) * 0.15) * o.width * p;
        ctx.globalAlpha = Math.max(0, Math.min(1, o.alpha * p * (0.72 + 0.28 * rng())));
        ctx.lineWidth = Math.max(0.02, gw * (0.55 + 0.45 * p));
        ctx.beginPath();
        ctx.moveTo(a[0] + nx * off, a[1] + ny * off);
        ctx.lineTo(b[0] + nx * off, b[1] + ny * off);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // A line between two points, drawn the way a hand draws a straight line:
  // slight bow, landing, and a quick lift.
  line(a, b, opts = {}) {
    const bow = (opts.bow ?? 0.25) * this.rng.gauss(1);
    const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    const d = dist(a, b) || 1;
    const nx = -(b[1] - a[1]) / d, ny = (b[0] - a[0]) / d;
    const pts = [a, [mid[0] + nx * bow, mid[1] + ny * bow], b];
    this.stroke(spline(pts, Math.max(4, Math.ceil(d / 3))), opts);
  }

  // A closed loop drawn in one or two passes. The start point overshoots
  // the way a quick hand closes a circle.
  ellipse(cx, cy, rx, ry, opts = {}) {
    const passes = opts.passes ?? 1;
    for (let k = 0; k < passes; k++) {
      const a0 = this.rng() * Math.PI * 2;
      const over = (opts.overshoot ?? 0.12) * (0.5 + this.rng());
      const jr = (opts.jitter ?? 0.012);
      const pts = arcPoints(cx, cy, rx * (1 + this.rng.gauss(jr)), ry * (1 + this.rng.gauss(jr)),
        a0, a0 + Math.PI * 2 * (1 + over), Math.max(24, Math.ceil((rx + ry) * 3)));
      this.stroke(pts, { taper: [0.05, 0.08], ...opts });
    }
  }

  circle(cx, cy, r, opts = {}) { this.ellipse(cx, cy, r, r, opts); }

  polygon(points, opts = {}) {
    for (let i = 0; i < points.length; i++) {
      const a = points[i], b = points[(i + 1) % points.length];
      // Corners overshoot a little, as when an architect draws a plan.
      const d = dist(a, b) || 1;
      const ux = (b[0] - a[0]) / d, uy = (b[1] - a[1]) / d;
      const o0 = (opts.overshoot ?? 0.6) * this.rng();
      const o1 = (opts.overshoot ?? 0.6) * this.rng();
      this.line([a[0] - ux * o0, a[1] - uy * o0], [b[0] + ux * o1, b[1] + uy * o1], opts);
    }
  }

  rect(x, y, w, h, opts = {}) {
    this.polygon([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], opts);
  }

  // Hatching inside a clip region. Each line is an individual stroke with
  // its own length, bow, and pressure, so a field of hatching never
  // repeats. opts: angle (radians), gap (mm), medium, width, alpha,
  // jitter (spacing irregularity), bounds [x, y, w, h].
  hatch(clipPath, bounds, opts = {}) {
    const o = { angle: Math.PI / 4, gap: 1.0, medium: "graphite", width: 0.18, alpha: 0.45,
      jitter: 0.25, grains: 2, wobble: 0.08, breaks: 0.0, density: null, run: 9, ...opts };
    const [bx, by, bw, bh] = bounds;
    const cx = bx + bw / 2, cy = by + bh / 2;
    const R = Math.hypot(bw, bh) / 2 + 2;
    const ux = Math.cos(o.angle), uy = Math.sin(o.angle);
    const nx = -uy, ny = ux;
    const run = () => {
      for (let s = -R; s <= R; s += o.gap * (1 + this.rng.gauss(o.jitter * 0.5))) {
        // A hand hatches a large field in overlapping runs of short
        // strokes, each with its own slight change of angle.
        let l = -R - this.rng() * o.run;
        while (l < R) {
          const len = o.run * (0.6 + 0.8 * this.rng());
          const da = this.rng.gauss(0.03);
          const vx = Math.cos(o.angle + da), vy = Math.sin(o.angle + da);
          const px = cx + nx * s + ux * l, py = cy + ny * s + uy * l;
          const mx = px + vx * len / 2, my = py + vy * len / 2;
          if (!o.density || this.rng() < o.density(mx, my)) {
            this.line([px, py], [px + vx * len, py + vy * len],
              { medium: o.medium, width: o.width, alpha: o.alpha * (0.7 + 0.5 * this.rng()), grains: o.grains,
                wobble: o.wobble, bow: 0.15, taper: [0.12, 0.3], breaks: o.breaks });
          }
          l += len * (0.85 + 0.25 * this.rng());
        }
      }
    };
    if (clipPath) this.sheet.clipAll(clipPath, run); else run();
  }

  // Short directional strokes that follow a field: for stone, water, and
  // foliage texture. pts: list of [x, y, angle, length].
  flicks(list, opts = {}) {
    for (const [x, y, ang, len] of list) {
      const ux = Math.cos(ang), uy = Math.sin(ang);
      this.line([x - ux * len / 2, y - uy * len / 2], [x + ux * len / 2, y + uy * len / 2],
        { taper: [0.3, 0.5], bow: 0.15, ...opts });
    }
  }

  // Smudge: a soft wash laid with a blending stump. Rendered with a blur so
  // the edge feathers, then broken by the paper at compose time.
  smudge(pathFn, { alpha = 0.12, blur = 1.2, medium = "wash" } = {}) {
    const ctx = this.sheet.ctx(medium);
    ctx.save();
    ctx.filter = `blur(${(blur * this.sheet.k).toFixed(1)}px)`;
    ctx.globalAlpha = alpha;
    ctx.fillStyle = medium === "chalk" ? "#fff" : "#000";
    ctx.beginPath();
    pathFn(ctx);
    ctx.fill();
    ctx.restore();
  }

  // Erase: a kneaded eraser pressed over a region removes the marks already
  // on the paper (and only those), so plates for lettering come clean.
  erase(pathFn, { strength = 0.9, blur = 0.6 } = {}) {
    for (const m of ["wash", "graphite", "charcoal"]) {
      const ctx = this.sheet.ctx(m);
      ctx.save();
      ctx.globalCompositeOperation = "destination-out";
      ctx.filter = `blur(${(blur * this.sheet.k).toFixed(1)}px)`;
      ctx.globalAlpha = strength;
      ctx.fillStyle = "#000";
      ctx.beginPath();
      pathFn(ctx);
      ctx.fill();
      ctx.restore();
    }
  }

  // Stippled tone: thousands of tiny pressed dots (a charcoal tip tapped
  // on the sheet). density(x, y) -> 0..1.
  stipple(bounds, density, { medium = "charcoal", size = 0.16, alpha = 0.6, count = 1000 } = {}) {
    const [bx, by, bw, bh] = bounds;
    const ctx = this.sheet.ctx(medium);
    ctx.save();
    ctx.fillStyle = medium === "chalk" ? "#fff" : "#000";
    for (let i = 0; i < count; i++) {
      const x = bx + this.rng() * bw, y = by + this.rng() * bh;
      if (this.rng() > density(x, y)) continue;
      ctx.globalAlpha = alpha * (0.5 + 0.5 * this.rng());
      ctx.beginPath();
      ctx.ellipse(x, y, size * (0.6 + this.rng()), size * (0.5 + 0.6 * this.rng()), this.rng() * 3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  // Cut guides. These are print furniture, not drawing: even dashed
  // lines laid on the graphite layer so scissors have a line to follow.
  _guide(ctxOp) {
    const ctx = this.sheet.ctx("graphite");
    ctx.save();
    ctx.setLineDash([1.4, 1.3]);
    ctx.strokeStyle = "#000";
    ctx.lineWidth = 0.22;
    ctx.globalAlpha = 0.75;
    ctx.beginPath();
    ctxOp(ctx);
    ctx.stroke();
    ctx.restore();
  }

  cutRect(x, y, w, h) { this._guide((c) => c.rect(x, y, w, h)); }

  cutCircle(cx, cy, r) { this._guide((c) => c.arc(cx, cy, r, 0, Math.PI * 2)); }
}
