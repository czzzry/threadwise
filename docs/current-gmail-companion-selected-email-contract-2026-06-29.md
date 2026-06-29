Status: Current contract note
Current as of: 2026-06-29
Builds on: `docs/prd.md`, `docs/issues/063-gmail-companion-sidebar-spine.md`

# Purpose

This note defines the selected-email contract for the Gmail companion sidebar spine.

Later slices should treat this as the shared contract frozen by slice `063`.

# Selected context sent from Gmail

The Gmail-mounted script sends this context to the local companion panel:

- `provider`
- `message_id`
- `thread_id`
- `subject`
- `sender`
- `page_url`
- `selected_at`

# Sidebar state returned by the local companion server

The current API response shape is:

- `contract_version`
- `generated_at`
- `selected_context`
- `selected_email`
- `daily_summary`
- `ui_state`

# Matching rules

The server resolves the selected email using:

1. exact `message_id` match against stored batch items
2. fallback match on normalized sender plus normalized subject

# Current boundaries

Slice `063` covers:

- Gmail-mounted sidebar shell
- minimizable panel
- selected-email category, status, and short reason
- compact daily summary

Slice `063` does not yet cover:

- `Correct / Teach`
- correction acknowledgments
- broader-impact preview
- unsubscribe execution flow
