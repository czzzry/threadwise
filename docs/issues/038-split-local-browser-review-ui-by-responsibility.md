# Title

Split local browser review UI by responsibility

## Type

Refactor

## User-visible goal

Keep the existing local browser workbench behavior unchanged while making the browser-review code easier to understand, safer to extend, and less likely to accumulate unrelated workflow logic in one file.

## Scope

- Split the current `src/local_browser_review_ui.py` module into a small set of files organized by responsibility
- Preserve the current public entrypoint and browser-visible behavior
- Keep stored-batch review, workbench rendering, shadow-evaluation views, and unsubscribe flows working exactly as they do now
- Extract only the clearest seams that already exist in practice, such as:
  - server/bootstrap wiring
  - stored-batch review routes and rendering
  - workbench/homepage rendering
  - shadow-evaluation rendering or handlers
  - unsubscribe inventory / execution handlers
- Keep the current local storage contracts and HTTP surface stable unless a tiny compatibility fix is required
- Strengthen or preserve tests around the current public behavior during the refactor

## Non-goals

- Changing product scope
- Redesigning the browser workbench UX
- Introducing a new frontend framework
- Rewriting the local HTTP server approach
- Refactoring unrelated Gmail, ProtonMail, reporting, or storage code unless directly required by the split
- Broad provider-abstraction work

## Acceptance criteria

- `src/local_browser_review_ui.py` is no longer the single home for the whole browser workbench behavior
- The resulting file structure makes the major responsibilities of the browser UI legible at a glance
- The existing public script entrypoint still works from the repo root
- Current browser-review behavior remains unchanged for stored-batch review, batch workbench, shadow-evaluation views, and unsubscribe actions
- Existing tests covering the browser UI still pass, with any additions focused on public behavior rather than internal implementation details

## Expected behavior

- Running `python3 scripts/review_local_batch_in_browser.py --help` still works from the repo root
- Launching the local browser workbench still serves the same routes and visible sections as before
- Stored review actions still persist to the same local storage contracts
- Shadow-evaluation pages still render through the same public flow
- Unsubscribe inventory and execution actions still behave the same from the founder’s perspective
- No new Gmail or ProtonMail mutation behavior is introduced through this refactor

## Expected tests or verification

- Run the existing browser-UI test suite and keep it green
- Add tests only if needed to pin current public behavior before moving code
- Verify the browser-review script still starts from the repo root without `PYTHONPATH` changes
- Manual smoke check that the workbench homepage, one stored batch, one shadow-evaluation view, and the unsubscribe section still load

## Dependencies/order

- This is a bounded maintenance slice that should happen before adding significantly more workbench behavior
- It is especially justified now that the workbench has grown to hold review, fetch, evaluation, and unsubscribe concerns
- Follow-on slices should reuse the new module boundaries rather than adding more behavior back into one file

## Stop conditions requiring Founder review

- The refactor starts changing visible workflow behavior instead of preserving it
- The split pressures the repo toward a framework migration rather than a bounded structural cleanup
- The work reveals that storage contracts or route semantics must change materially
- The effort expands into a broad multi-module architecture rewrite rather than one focused seam cleanup
