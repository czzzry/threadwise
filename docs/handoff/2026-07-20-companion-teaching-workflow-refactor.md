# Companion Teaching Workflow Refactor Handoff

Status: Completed bounded architecture refactor
Current as of: 2026-07-20
Builds on: `CONTEXT.md`, `docs/v2-alignment.md`, and `docs/handoff/2026-07-20-gmail-companion-rendering-refactor.md`

## Outcome

The companion's teaching apply path now delegates the complete local lesson-to-outcome workflow to `CompanionTeachingWorkflow`.

The workflow owns:

- safety and included-message validation
- application of the local teaching lesson
- construction of one typed provider write request
- user-facing acknowledgment and structured outcome semantics

`GmailCompanionApp` retains transport concerns, analytics, asynchronous sidebar refresh, and the Gmail-specific mutation implementation. The provider mutation crosses an injected callable boundary, so workflow tests do not need credentials, a Gmail client, or a live inbox.

The application module decreased from 1,942 lines after the rendering refactor to 1,853 lines.

## Behavior and safety decisions

- The ordinary teaching path still rejects suspicious-email changes before any local or provider mutation.
- Gmail write behavior, modes, labels, inbox removal, and error handling are unchanged.
- Existing teaching acknowledgment and outcome payloads are preserved.
- Gmail-specific mutation mechanics remain in the app-side adapter; the domain workflow knows only the immutable `TeachingWriteRequest` contract.
- No live inbox, credentials, extension session, or provider mutation was accessed.

## Validation

- Failing-first tests characterized the missing workflow module and provider boundary.
- Dedicated workflow tests cover request construction, exact outcome semantics, and rejection before mutation.
- Companion coordination tests now substitute the workflow result rather than patching internal teaching functions and response helpers.
- `python3 -m unittest discover -s tests`: 724 tests passed.
- Python compilation passed for the workflow and application modules.
- Diff whitespace checks passed.

## Remaining architecture opportunities

- The Gmail write-through implementation is still a sizeable provider-specific method. Extract it only as a separately triaged slice with mock-client characterization of label and inbox-removal semantics.
- Local artifact access and classifier-decision locality remain broader, higher-risk follow-up candidates.
