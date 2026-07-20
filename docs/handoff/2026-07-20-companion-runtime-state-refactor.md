# Companion Runtime State Refactor Handoff

Status: Completed bounded architecture refactor
Current as of: 2026-07-20
Builds on: `docs/handoff/2026-07-20-gmail-teaching-adapter-refactor.md` and the refreshed 2026-07-20 architecture review

## Outcome

Cached companion state now lives in one deep `CompanionRuntimeState` module. It owns:

- sidebar and harness snapshots
- runtime, daily-summary, unsubscribe, live-inbox-ID, and harness caches
- cache invalidation
- selected-email live-understanding overlays
- handled-review acknowledgment refresh
- asynchronous teaching follow-up state and recent activity

The application retains a small provider-read adapter that loads current Gmail Inbox IDs. The runtime module receives that adapter as a callable and owns its cache, so it has no credential or Gmail-client dependency.

The application module decreased from 1,419 to 1,196 lines. The runtime module is 315 lines behind snapshot, invalidation, acknowledgment, refresh, runtime-payload, and unsubscribe-candidate interfaces.

## Behavior and testability decisions

- The default background runner still uses a daemon thread.
- Tests inject a deterministic background runner, eliminating temp-directory cleanup races from async refresh coverage.
- Refresh still exposes `working`, then `done` or `retry`, and primes the harness cache only after the final state is set.
- Live selected-email understanding remains recomputed on each harness read even when the broader harness payload is cached.
- No live inbox, credentials, extension session, or provider mutation was accessed.

## Validation

- Failing-first tests proved the runtime module did not exist.
- Direct runtime tests cover cache reuse and invalidation, deterministic refresh completion, retry activity, and the injected live-inbox-ID adapter.
- Existing companion, analytics, unsubscribe, and handled-review tests now use the runtime interface instead of application internals.
- `python3 -m unittest discover -s tests`: 730 tests passed.
- Python compilation and diff whitespace checks passed.

## Remaining architecture opportunities

- Provider message normalization still repeats canonical message assembly; preserve provider-specific parsing while testing whether shared assembly passes the deletion test.
- HTTP transport extraction remains speculative because it may only move the route tree without increasing depth.
