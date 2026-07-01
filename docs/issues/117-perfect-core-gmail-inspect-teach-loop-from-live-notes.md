# Perfect Core Gmail Inspect/Teach Loop from Live Notes

Status: Implemented local tranche

## Problem

Founder live testing showed the core daily-use loop was still not obvious enough:

- Threadwise could appear stuck on a previously inspected email after opening Gmail.
- A stored Threadwise email could be visible in Agent View without an obvious way to open the actual Gmail email for inspection.
- "What Changed Today" rows looked clickable, but did not clearly explain whether they previewed in Threadwise or opened Gmail.
- Correct / Teach and feedback textareas could visually overflow the sidebar.

## User Story

As a Threadwise user, I want to open Gmail, inspect a categorized email, open the actual email in Gmail when needed, talk to the LLM, and correct the category without hunting through the UI.

## Scope

- Treat Gmail list-row DOM artifacts as non-selected unless Gmail exposes an opened message subject.
- Add a clear `Open this email in Gmail` action to selected Agent View emails.
- Split changed-today row actions into explicit `Preview in Threadwise` and `Open in Gmail`.
- Keep teach and note inputs inside the sidebar width.

## Out of Scope

- LinkedIn unsubscribe provider-error handling.
- Full Correct / Teach redesign.
- Multi-label selector and `Unsure` interaction.
- Dashboard needs-attention interaction redesign.

## Validation

- JavaScript syntax check.
- Focused companion UI contract test.
- Full test discovery before marking complete.

## AFK hardening follow-up

Added a regression guard for the Przelewy/phishing teaching path:

- `Preview lesson` may surface broader similar candidates from same domain/display sender/subject pattern.
- `Apply to matching emails too` remains limited to exact stored proposal matches.
- Broader similar candidates stay review-only and are not silently relabeled by the existing matching-existing action.

This preserves the current product boundary: broader rules and broader similar-email application need a separate confirmation design.
