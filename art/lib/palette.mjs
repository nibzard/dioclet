// The colour edition's palette. The brand colours (charcoal, imperial
// red, antique gold, roman stone) carry the frames, plaques and play
// marks; earth, leaf and sea colours carry the plan. Glazes multiply on
// a warm paper, so every colour here is the colour of one full-strength
// wash, and overlaps go darker the way watercolour does.
//
// The gates take the colour of their names (golden, silver, bronze,
// iron), not of a player: names and colours belong to players, and any
// player may start at any gate.
export const PALETTE = {
  paper: "#fbf5e8",
  ink: "#2b2622",          // charcoal: a warm sepia-black for every line

  red: "#9b2423",          // imperial red
  redLight: "#d9837a",
  gold: "#c39a45",         // antique gold
  goldLight: "#ead39a",
  stone: "#ddd2bf",        // roman stone
  stoneDark: "#b8a68a",
  marble: "#f1ebe0",
  plaque: "#f2e3b8",

  street: "#e7dcc6",
  ground: "#ece3c9",
  court: "#efe4c8",
  wall: "#cdbb98",
  roof: "#c46a4c",         // terracotta tiles
  roofShade: "#a2533c",
  dome: "#9aa9ae",         // lead
  shadow: "#8c8aa3",       // cool shadow under every building
  leaf: "#869a4e",
  cypress: "#56704a",
  sea: "#6aa2bc",
  seaDeep: "#4f86a2",
  wood: "#a8794d",
  steel: "#a9b6bf",
  bronze: "#b9814a",
  leather: "#8a5a3a",

  gates: { P0: "#d1a640", P1: "#b7c0c6", P2: "#b77845", P3: "#6f7880" },
  factions: { army: "#a8332b", officials: "#6d4f8f", elites: "#6f8f3a" },
  factionBack: "#6f8a9c",
  players: ["#a8332b", "#2f6c98", "#4f8a3c", "#d39b26"],
};
