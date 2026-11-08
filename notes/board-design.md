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

## Six-block correction, 2026-11-08

The designer rejects V0.7.2 because its added central lane creates eight physical blocks. V0.7.3 removes that lane, keeps six solid 5×5 blocks, and aligns both north and south gates with the existing western street. The cardo is off-center; the decumanus retains the east and west gates. Each block has an explicit district assignment.

The active rules source is `rules_v073_sixblocks_cardo.json`. Both generators validate six connected blocks, complete blocked footprints, one entry per block, main-street continuity, and gate endpoints. The old eight-block map fails that contract. The geometry is not claimed to have equal gate strength.

The full design intervention is recorded in `docs/intervention-plan.md`. It includes persistent equipment, faction support, Prestige, a contested succession, and seeded random gate assignment. Those mechanics remain a separate prototype after the immediate board correction.

Verification of V0.7.3: 135 Python tests pass; the JavaScript engine completes 40 bot games; the interface completes a full game and replay. Desktop and 390-pixel mobile browser checks show six distinct district blocks. The deployed board independently reports six connected blocked groups of 25 cells each and 97 street spaces. Deployment version: `5f11cb62-58af-4e6a-a121-ff7c550c1a87`.

## Markers by phase, 2026-11-08

The browser renderer previously drew both phases at once. The inactive Emperor circle covered the south gate during the city phase, and palace tooltips overwrote city tooltips.

Palace markers now share a layer that is hidden in the city phase. The Emperor, retreat, seal badges, legend, hit areas, and tooltips switch with the phase. The city shows the south gate and checkpoint. Returning to a city game through replay resets the layer and labels.

Interface regression checks cover initial setup, a city game, a palace game, return to the city, and a full game with replay. They also verify that the colored Emperor and retreat circles belong to the hidden layer.
