# Gmail Companion Rendering Refactor Handoff

Status: Completed bounded architecture refactor
Current as of: 2026-07-20
Builds on: `CONTEXT.md`, `docs/v2-alignment.md`, and the 2026-07-20 architecture review

## Outcome

The Gmail companion application now delegates complete page composition to one deep rendering module.

The renderer owns:

- the static Gmail panel shell
- the simulator page
- the installation page
- the unsubscribe-review page
- the daily dashboard page
- page-level escaping, script-safe JSON, grouping, and existing card/row rendering helpers

`GmailCompanionApp` retains thin compatibility methods plus application responsibilities: request routing, state and artifact loading, caches, teaching workflows, analytics, Gmail checks, and bounded provider actions.

The application module decreased from 5,396 lines at architecture-review time to 1,942 lines. The renderer grew from 268 lines to 3,763 lines because it now hides the complete HTML, CSS, and browser-script implementation behind five small page interfaces.

## Behavior and security decisions

- Existing application render methods remain callable, so current tests and callers keep their interface.
- Dashboard state loading remains in the application; the renderer receives prepared view data and performs only presentation-specific deduplication and composition.
- Unsubscribe candidate loading remains in the application; the renderer owns grouping, focus state, action copy, and safe candidate-key embedding.
- Installation-page runtime values are now HTML-escaped before interpolation.
- A pre-existing invalid Python escape warning in embedded simulator JavaScript was removed without changing the emitted regular expression.

## Validation

- Red tests first proved that complete-page renderer interfaces did not exist.
- Direct renderer tests cover installation escaping, unsubscribe grouping/focus/script safety, dashboard view data, and static panel/simulator ownership.
- Existing companion behavior tests cover the compatibility methods and product contracts.
- `python3 -m unittest discover -s tests`: 722 tests passed.
- Python compilation with `SyntaxWarning` treated as an error passed for the rendering and application modules.
- Diff whitespace checks passed.

No live inbox, credentials, extension session, or provider mutation was accessed.

## Remaining architecture opportunities

- The rendering module is intentionally deep and large; splitting it by file size alone would recreate shallow modules. Extract static assets only if a concrete build or browser-cache need appears.
- The teaching preview-to-outcome candidate was completed in `docs/handoff/2026-07-20-companion-teaching-workflow-refactor.md`.
- Local artifact access and classifier-decision locality remain broader, higher-risk follow-up candidates.
