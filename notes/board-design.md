# Board design review

Research date: 2026-11-07.

Source: [Live board](https://dioclet-board.nikola-balic.workers.dev/).
Local sources: `web/`, `wrangler.jsonc`, and `tools/test_web_ui.mjs`.

## Verified findings

- The live board uses V0.7. The workspace already contains unpublished V0.7.1 gate changes.
- The live engine and bots match the workspace files byte for byte.
- The design uses limestone tones, green controls, six district cards, and a palace illustration.
- The setup, rulebook, and end dialog manage keyboard focus.
- Available moves support Enter and Space. Mobile screens have a board zoom control.
- Browser checks cover desktop, 390-pixel mobile, and 320-pixel mobile layouts.
- The engine test completes 40 bot games. The interface test completes a game and checks replay resets.
- Both V0.7 and V0.7.1 configurations pass the interface test.

## Deployment scope

The deployment folder is `/tmp/dioclet-design-deploy`. It contains the new interface and the verified live V0.7 game data. Its rulebook uses “city blocks” to match the new colors. The workspace retains the existing V0.7.1 game changes.

Run the interface test from `/tmp/dioclet-ui-check`, where `jsdom` is installed:

```bash
node /home/agent/dioclet/tools/test_web_ui.mjs
```

The deployment configuration is `/tmp/dioclet-design-deploy/wrangler.jsonc`.

## Open questions

The separate V0.7.1 gate update awaits its own release decision.
