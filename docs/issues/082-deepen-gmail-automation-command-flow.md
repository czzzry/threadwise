# Status

Completed
Current as of: 2026-06-30
Triage state: `ready-for-agent`
Builds on: `docs/issues/081-deepen-teaching-loop-module.md`

# Title

Deepen Gmail automation command flow without widening autonomy

## Type

AFK / Refactor / Pre-MVP+2

## What to build

Extract the shared Gmail automation orchestration behind the live Gmail command modules into a dedicated Gmail automation module while preserving the existing command names, arguments, output contracts, and safety boundaries.

The new module should own reusable behavior for auto-approve selection, Gmail writer construction, label write-back, low-value `INBOX` removal summaries, retry candidate handling, and daily-run execution glue. Existing CLI files should remain public entrypoints that parse args, resolve paths, ask for explicit confirmation where they already do, and print results.

This is behavior-preserving. Do not add new Gmail autonomy, new labels, scheduling, background sync, delete/trash/archive/send/reply behavior, ProtonMail mutation, or generic provider write abstractions.

## Acceptance criteria

- [x] A Gmail automation module exposes reusable functions for the current live Gmail automation commands.
- [x] Existing script names, CLI arguments, confirmation prompts, and exit behavior stay unchanged.
- [x] Daily run behavior is unchanged: fetch, auto-approve eligible items, write `EA/` labels, remove `INBOX` through the existing gate, and write the daily report.
- [x] Auto-apply behavior is unchanged, including explicit `AUTOAPPLY` confirmation.
- [x] Low-value `INBOX` removal behavior is unchanged, including explicit `REMOVE` confirmation and the successful-writeback gate.
- [x] Retry behavior is unchanged: only latest failed writes are retried, and changed labels remain blocked.
- [x] Gmail safety boundaries remain unchanged per `docs/decisions/gmail-bounded-autonomy.md`.
- [x] Focused module tests and existing CLI tests pass.

## Blocked by

None - can start immediately.
