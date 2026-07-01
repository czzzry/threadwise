# Trigger Gmail check from dashboard

Status: Ready for agent
Type: AFK
GitHub issue: `#12`
Parent: GitHub issue `#7`; `docs/prd.md`

## What to build

Add a product-facing **Run Gmail check** flow to the Threadwise dashboard, with sidebar status linking into it.

The founder should not need to remember developer commands to trigger the daily Gmail loop. The dashboard button should require confirmation, disclose safe Gmail mutations and possible LLM cost, block duplicate active runs, and show run status.

## Acceptance criteria

- [ ] The dashboard exposes a Run Gmail check action.
- [ ] The action requires confirmation before starting.
- [ ] Confirmation copy states that the run may apply existing safe `EA/` labels, remove `INBOX` only for low-value allowed categories, and call the LLM for attention detection.
- [ ] While a run is active, duplicate run requests are blocked.
- [ ] The UI shows idle, running, succeeded, and failed states.
- [ ] The dashboard-triggered run uses the same safe Gmail mutation boundaries as the existing daily run.
- [ ] Attention detection remains non-mutating.
- [ ] The Gmail companion sidebar shows connection/run status and links to the dashboard run flow.
- [ ] Tests cover confirmation, duplicate protection, success, failure, and unchanged Gmail safety boundaries.

## Blocked by

- GitHub issue `#9`; `docs/issues/084-generate-gmail-attention-candidates-with-llm.md`
- GitHub issue `#10`; `docs/issues/085-show-needs-attention-in-daily-dashboard.md`
