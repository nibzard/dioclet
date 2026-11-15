// Render the art assets for the drawn print kits.
//
//   node render.mjs [piece ...] [--dpi N] [--out DIR] [--color]
//
// Without --color the assets are the grayscale edition, in build/assets.
// With --color they are the full-colour edition (the same drawing with
// watercolour glazes), in build/assets-color.
// Pieces: palace, succession, cards, factions, tokens (default: all). Geometry comes
// from build/layout.json; run `python3 art/export_layout.py` first.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : dflt;
};
const dpiArg = opt("--dpi", null);
const color = args.includes("--color");
const outDir = opt("--out", join(here, "build", color ? "assets-color" : "assets"));
const flags = new Set(["--dpi", "--out"]);
const pieces = args.filter((x, i) => !x.startsWith("--") && !flags.has(args[i - 1]));
const want = (p) => pieces.length === 0 || pieces.includes(p);
const layout = JSON.parse(readFileSync(join(here, "build", "layout.json"), "utf8"));
mkdirSync(outDir, { recursive: true });
if (color) {
  const { useColor } = await import("./lib/core.mjs");
  const { PALETTE } = await import("./lib/palette.mjs");
  useColor(PALETTE);
}

const save = (name, canvas) => {
  const path = join(outDir, name);
  writeFileSync(path, canvas.toBuffer("image/png"));
  console.log(`  ${name} ${canvas.width}x${canvas.height}`);
};

const t0 = Date.now();
if (want("palace")) {
  const { renderPalace } = await import("./pieces/palace.mjs");
  save("palace-board.png", renderPalace(layout, { dpi: Number(dpiArg || 200) }));
}
if (want("succession")) {
  const { renderSuccession } = await import("./pieces/succession.mjs");
  save("succession-map.png", renderSuccession(layout, { dpi: Number(dpiArg || 200) }));
}
if (want("cards")) {
  const { renderCards, renderBack } = await import("./pieces/cards.mjs");
  for (const [name, canvas] of renderCards(layout, { dpi: Number(dpiArg || 300) })) save(name, canvas);
  save("card-back.png", renderBack(layout, { dpi: Number(dpiArg || 300) }));
}
if (want("factions")) {
  const { renderFactionCards, renderFactionBack } = await import("./pieces/cards.mjs");
  for (const [name, canvas] of renderFactionCards(layout, { dpi: Number(dpiArg || 300) })) save(name, canvas);
  save("faction-back.png", renderFactionBack(layout, { dpi: Number(dpiArg || 300) }));
}
if (want("tokens")) {
  const { renderTokens } = await import("./pieces/tokens.mjs");
  for (const [name, canvas] of renderTokens(layout, { dpi: Number(dpiArg || 300) })) save(name, canvas);
}
console.log(`rendered in ${((Date.now() - t0) / 1000).toFixed(1)} s -> ${outDir}`);
