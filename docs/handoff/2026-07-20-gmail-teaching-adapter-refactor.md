# Gmail Teaching Adapter Refactor Handoff

Status: Completed bounded architecture refactor
Current as of: 2026-07-20
Builds on: `docs/handoff/2026-07-20-companion-teaching-workflow-refactor.md` and the refreshed 2026-07-20 architecture review

## Outcome

Gmail-specific teaching preview and mutation mechanics now live behind the two-method `GmailTeachingAdapter` interface:

- `preview_backfill(preview)` owns Gmail search construction, bounded candidate inspection, normalization, semantic filtering, and confirmation estimates.
- `apply(request)` owns client initialization, stored-batch replay, explicitly included live-message mutation, audit artifacts, and exact write summaries.

The companion application now constructs the adapter and passes its `apply` method into `CompanionTeachingWorkflow`. It no longer owns provider-write loops, backfill search semantics, mutation artifact construction, or partial-failure aggregation.

The application module decreased from 1,793 to 1,419 lines. The adapter is 377 lines behind two interfaces, giving it substantially more depth than the implementation it removed from the app.

## Behavior and safety decisions

- The immutable `TeachingWriteRequest` remains the provider-write seam.
- Future-rule-only and disabled modes still short-circuit before Gmail client creation.
- Included-message application still mutates only the exact confirmed message IDs and excludes already-replayed local IDs.
- Label success, label failure, Inbox-removal success, and Inbox-removal failure remain independently aggregated and audited.
- No generic provider-write framework was introduced.
- No live inbox, credentials, extension session, or real provider mutation was accessed.

## Validation

- Failing-first adapter tests proved the new interface did not exist.
- Direct adapter tests cover semantic Gmail query behavior, future-rule short-circuiting, and client-initialization failures.
- Existing companion tests cover real interface composition with fake Gmail clients: bounded live preview, local replay, included-message backfill, and partial label/Inbox failures.
- `python3 -m unittest discover -s tests`: 729 tests passed.
- Python compilation and diff whitespace checks passed.

## Remaining architecture opportunities

- Companion runtime state and cache invalidation remain split across the application and pure state helpers; deepen them only if characterization yields a smaller snapshot interface.
- Provider message normalization still repeats canonical message assembly; preserve provider-specific parsing while testing whether shared assembly passes the deletion test.
- HTTP transport extraction remains speculative because it may only move the route tree without increasing depth.
