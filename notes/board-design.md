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

## Design update, 2026-11-08

The user prefers square corners and no colored accents on one border edge. Cards, dialogs, controls, labels, and rectangular board details now use square corners. The active player uses a background tint and an even border. Rulebook notes use an even border.

The live assets now match the workspace before this update, including the board data. This deployment changes only `style.css` and `app.js`. The deployment folder is `/tmp/dioclet-square-deploy`. Browser checks confirm square corners and equal border widths on desktop and mobile.

## Action choices, 2026-11-08

The user could not see the choice menu below the player cards. Clicking a treasure now collects it automatically when no competing action exists. When a rival creates a duel option, the interface presents collection and dueling in a modal. It omits the redundant walk option at an available treasure. Cancel, Escape, and backdrop clicks dismiss the modal without using the turn.

The special marker also covered its movement highlight and extended beyond its clickable circle. The circle now covers the whole marker and shows an outer highlight. Browser checks reproduce an edge click and verify the mobile modal. Interface tests cover automatic collection, competing actions, cancellation, focus, a complete game, and replay.

The deployment folder is `/tmp/dioclet-treasure-deploy`. It preserves the live board data. Concurrent workspace changes to the V0.7.2 board remain separate from this interface update.
