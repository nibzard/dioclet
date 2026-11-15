// Core of the drawing system: seeded randomness, value noise, the paper,
// and the media layers.
//
// The artwork is a grayscale drawing on light paper, made for laser
// printers. Each medium (graphite, charcoal, wash, chalk) draws on its own
// layer. Nothing is "textured" afterwards: at compose time every layer
// deposits on the paper according to the paper's tooth, so a grainy
// charcoal stroke skips the valleys of the sheet and a wash fills them.
import { createCanvas } from "@napi-rs/canvas";

// ---------------------------------------------------------------------------
// Randomness. One seeded generator per artwork keeps every render
// identical for the same seed.

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function makeRng(seed) {
  const next = mulberry32(seed);
  const rng = () => next();
  rng.range = (a, b) => a + (b - a) * next();
  rng.int = (a, b) => Math.floor(a + (b - a + 1) * next());
  rng.pick = (list) => list[Math.floor(next() * list.length)];
  rng.chance = (p) => next() < p;
  // Approximately normal: the sum of three uniforms.
  rng.gauss = (sd = 1) => (next() + next() + next() - 1.5) * 2 * sd;
  rng.fork = (salt) => makeRng((seed * 2654435761 + salt * 40503) >>> 0);
  return rng;
}

// Smooth 1D and 2D value noise in [-1, 1]. The hand wobbles and the
// paper fibres both come from this.
export function makeNoise(seed) {
  const r = mulberry32(seed);
  const N = 512;
  const perm = new Uint16Array(N * 2);
  const vals = new Float32Array(N);
  for (let i = 0; i < N; i++) { perm[i] = i; vals[i] = r() * 2 - 1; }
  for (let i = N - 1; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [perm[i], perm[j]] = [perm[j], perm[i]];
  }
  for (let i = 0; i < N; i++) perm[N + i] = perm[i];
  const fade = (t) => t * t * (3 - 2 * t);
  const n1 = (x) => {
    const xi = Math.floor(x), xf = x - xi;
    const a = vals[perm[xi & (N - 1)]], b = vals[perm[(xi + 1) & (N - 1)]];
    return a + (b - a) * fade(xf);
  };
  const n2 = (x, y) => {
    const xi = Math.floor(x), yi = Math.floor(y);
    const xf = x - xi, yf = y - yi;
    const h = (i, j) => vals[perm[(perm[i & (N - 1)] + j) & (N - 1)]];
    const u = fade(xf), v = fade(yf);
    const a = h(xi, yi), b = h(xi + 1, yi), c = h(xi, yi + 1), d = h(xi + 1, yi + 1);
    return (a + (b - a) * u) * (1 - v) + (c + (d - c) * u) * v;
  };
  const fbm2 = (x, y, oct = 4) => {
    let s = 0, amp = 0.5, f = 1, norm = 0;
    for (let o = 0; o < oct; o++) { s += amp * n2(x * f, y * f); norm += amp; amp *= 0.5; f *= 2.03; }
    return s / norm;
  };
  return { n1, n2, fbm2 };
}

// ---------------------------------------------------------------------------
// The sheet. A Sheet holds the media layers at a fixed resolution and
// works in millimetres: every drawing call passes mm, the sheet scales.

export const MEDIA = ["wash", "graphite", "charcoal", "chalk"];

// The colour edition. useColor(palette) switches every Sheet made after
// it to colour: a warm paper, a sepia-black ink, and one more layer,
// "pigment", that holds transparent watercolour glazes. The grayscale
// edition never calls it, so its renders stay byte-identical.
let colorPalette = null;
export function useColor(palette) { colorPalette = palette; }
export const isColor = () => colorPalette !== null;

const hexRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);

export class Sheet {
  constructor({ widthMm, heightMm, dpi, seed, paper = {}, color = colorPalette }) {
    this.widthMm = widthMm;
    this.heightMm = heightMm;
    this.dpi = dpi;
    this.k = dpi / 25.4;                       // pixels per mm
    this.w = Math.round(widthMm * this.k);
    this.h = Math.round(heightMm * this.k);
    this.seed = seed;
    this.rng = makeRng(seed);
    this.noise = makeNoise(seed ^ 0x5eed);
    this.paper = { tone: 0.985, fibre: 0.018, tooth: 1.0, ...paper };
    this.color = color;
    this.media = color ? [...MEDIA, "pigment"] : MEDIA;
    this.layers = {};
    for (const m of this.media) {
      const canvas = createCanvas(this.w, this.h);
      const ctx = canvas.getContext("2d");
      ctx.scale(this.k, this.k);               // draw in mm
      ctx.lineJoin = "round";
      this.layers[m] = { canvas, ctx };
    }
  }

  ctx(medium) { return this.layers[medium].ctx; }

  // Run fn(ctx) for every medium layer with the same clip path. Callers
  // use this to keep hatching inside a block or a coin.
  clipAll(pathFn, fn) {
    for (const m of this.media) {
      const c = this.ctx(m);
      c.save();
      c.beginPath();
      pathFn(c);
      c.clip();
    }
    try { fn(); } finally { for (const m of this.media) this.ctx(m).restore(); }
  }

  // Paper tooth in [0, 1] at pixel (x, y): laid lines, fibres, and a
  // fine random grain. High tooth catches dry pigment.
  _toothField() {
    const { w, h, k } = this;
    const tooth = new Float32Array(w * h);
    const tone = new Float32Array(w * h);
    const nz = this.noise;
    const r = mulberry32(this.seed ^ 0x7007);
    const laid = 1.05 * k;                   // laid-line pitch, about 1 mm
    for (let y = 0; y < h; y++) {
      const ym = y / k;
      for (let x = 0; x < w; x++) {
        const xm = x / k;
        // Fine grain: per-pixel jitter mixed with 0.25 mm noise.
        const g = nz.n2(xm * 4.1, ym * 4.3) * 0.5 + nz.n2(xm * 9.7 + 31, ym * 9.1 - 7) * 0.35 + (r() - 0.5) * 0.45;
        // Laid lines run horizontally, chain lines every 25 mm.
        const ll = Math.cos((y / laid) * Math.PI * 2 + nz.n1(xm * 0.08) * 1.2) * 0.22;
        const cl = Math.exp(-Math.pow(((xm % 25) - 12.5) / 0.35, 2)) * 0.25;
        const t = 0.5 + 0.5 * Math.tanh((g + ll + cl) * 1.6);
        tooth[y * w + x] = t;
        // Paper tone: large soft mottling and short fibres.
        const mott = nz.fbm2(xm * 0.012, ym * 0.012, 3);
        const fib = Math.max(0, nz.n2(xm * 1.7 + ym * 0.6, ym * 1.3 - xm * 0.2) - 0.62) * 2.0;
        tone[y * w + x] = this.paper.tone + mott * this.paper.fibre - fib * 0.006;
      }
    }
    return { tooth, tone };
  }

  // Flatten every medium onto the paper. Returns a grayscale RGBA canvas,
  // or a colour one when the sheet is in colour.
  compose({ mask } = {}) {
    if (this.color) return this._composeColor({ mask });
    const { w, h } = this;
    // An optional mask (drawn in mm by the caller) gives the output an
    // alpha channel: tokens keep a transparent background outside their
    // cut line.
    let maskData = null;
    if (mask) {
      const mc = createCanvas(w, h);
      const mctx = mc.getContext("2d");
      mctx.scale(this.k, this.k);
      mctx.fillStyle = "#000";
      mctx.beginPath();
      mask(mctx);
      mctx.fill();
      maskData = mctx.getImageData(0, 0, w, h).data;
    }
    const { tooth, tone } = this._toothField();
    const data = {};
    for (const m of MEDIA) {
      data[m] = this.layers[m].ctx.getImageData(0, 0, w, h).data;
    }
    const out = createCanvas(w, h);
    const octx = out.getContext("2d");
    const img = octx.createImageData(w, h);
    const o = img.data;
    const toothAmt = this.paper.tooth;
    for (let i = 0, p = 0; i < w * h; i++, p += 4) {
      const t = tooth[i];
      // Layer darkness = alpha * (1 - luminance). Layers hold black ink
      // or, for chalk, white.
      const wa = data.wash[p + 3] / 255 * (1 - data.wash[p] / 255);
      const ga = data.graphite[p + 3] / 255 * (1 - data.graphite[p] / 255);
      const ca = data.charcoal[p + 3] / 255 * (1 - data.charcoal[p] / 255);
      const ch = data.chalk[p + 3] / 255;
      // Dry media: deposition rises with tooth. Charcoal is the grainiest.
      const gDep = ga * (1 - toothAmt * 0.5 * (1 - t) - 0.08 * (1 - ga));
      const cDep = ca * (1 - toothAmt * 0.78 * Math.pow(1 - t, 1.3)) ;
      // Wash pools in the valleys a little (the opposite of dry media).
      const wDep = wa * (0.88 + 0.24 * (1 - t) * toothAmt);
      let v = tone[i];
      v *= 1 - Math.min(1, wDep);
      v *= 1 - Math.min(1, gDep * 0.92);
      v *= 1 - Math.min(1, cDep);
      // Chalk lifts tone back toward white, mostly on the peaks.
      v += (1 - v) * Math.min(1, ch * (0.35 + 0.65 * t));
      const g8 = Math.max(0, Math.min(255, Math.round(v * 255)));
      o[p] = o[p + 1] = o[p + 2] = g8;
      o[p + 3] = maskData ? maskData[p + 3] : 255;
    }
    octx.putImageData(img, 0, 0);
    return out;
  }

  _maskData(mask) {
    if (!mask) return null;
    const mc = createCanvas(this.w, this.h);
    const mctx = mc.getContext("2d");
    mctx.scale(this.k, this.k);
    mctx.fillStyle = "#000";
    mctx.beginPath();
    mask(mctx);
    mctx.fill();
    return mctx.getImageData(0, 0, this.w, this.h).data;
  }

  // The colour compose. The pigment layer is a transparent glaze: each
  // channel filters the light by its colour, more where the paper's
  // valleys hold water (granulation) and a little unevenly across the
  // sheet (blooms). The dry media then deposit exactly as in the
  // grayscale compose, but in a sepia-black ink, and chalk lifts back
  // toward the paper colour.
  _composeColor({ mask } = {}) {
    const { w, h } = this;
    const maskData = this._maskData(mask);
    const { tooth, tone } = this._toothField();
    const data = {};
    for (const m of this.media) data[m] = this.layers[m].ctx.getImageData(0, 0, w, h).data;
    const paper = hexRgb(this.color.paper);
    const ink = hexRgb(this.color.ink);
    const nz = makeNoise(this.seed ^ 0xb100);
    const out = createCanvas(w, h);
    const octx = out.getContext("2d");
    const img = octx.createImageData(w, h);
    const o = img.data;
    const toothAmt = this.paper.tooth;
    const pg = data.pigment;
    for (let y = 0, i = 0, p = 0; y < h; y++) {
      for (let x = 0; x < w; x++, i++, p += 4) {
        const t = tooth[i];
        const wa = data.wash[p + 3] / 255 * (1 - data.wash[p] / 255);
        const ga = data.graphite[p + 3] / 255 * (1 - data.graphite[p] / 255);
        const ca = data.charcoal[p + 3] / 255 * (1 - data.charcoal[p] / 255);
        const ch = data.chalk[p + 3] / 255;
        const gDep = ga * (1 - toothAmt * 0.5 * (1 - t) - 0.08 * (1 - ga));
        const cDep = ca * (1 - toothAmt * 0.78 * Math.pow(1 - t, 1.3));
        const wDep = wa * (0.88 + 0.24 * (1 - t) * toothAmt);
        // Ink darkness as one value; it tints toward the ink colour.
        let keep = (1 - Math.min(1, wDep)) * (1 - Math.min(1, gDep * 0.92)) * (1 - Math.min(1, cDep));
        const pa = pg[p + 3] / 255;
        let bloom = 1;
        if (pa > 0) bloom = (0.86 + 0.28 * (1 - t)) * (1 + 0.14 * nz.fbm2(x / this.k * 0.08, y / this.k * 0.08, 3));
        const lift = Math.min(1, ch * (0.35 + 0.65 * t));
        for (let c = 0; c < 3; c++) {
          let v = tone[i] / this.paper.tone * paper[c];
          if (pa > 0) v *= 1 - Math.min(1, pa * bloom) * (1 - pg[p + c] / 255);
          v *= keep + (1 - keep) * ink[c];
          v += (paper[c] - v) * lift;
          o[p + c] = Math.max(0, Math.min(255, Math.round(v * 255)));
        }
        o[p + 3] = maskData ? maskData[p + 3] : 255;
      }
    }
    octx.putImageData(img, 0, 0);
    return out;
  }

  release() {
    for (const m of this.media) this.layers[m].canvas.width = 1;
    this.layers = {};
  }
}
