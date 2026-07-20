# Public Data Policy

Threadwise is developed against private local inbox data, but the public repository must remain safe to clone, index, and redistribute.

## What may be committed

- synthetic messages created specifically for tests and demos
- transformed examples that use fictional people, reserved `example.*` addresses, and non-identifying content
- provider documentation examples and public role-based service addresses when a provider-specific rule genuinely requires them
- screenshots and demos generated from the synthetic fixture set

## What must stay local

- OAuth credentials, API tokens, cookies, browser profiles, and environment files
- raw or normalized mailbox exports
- real personal sender or recipient addresses
- personal names, account identifiers, message IDs, subjects, or bodies copied from a live mailbox
- absolute workstation paths and host-specific configuration

Local data directories are excluded in `.gitignore`. CI also runs `scripts/check_public_data_hygiene.py` to catch common consumer mailbox addresses, workstation home paths, tracked OS metadata, unsanitized live-account evidence markers, and non-reserved email domains in the public demo before changes reach `main`.

Public QA records must include a `Data classification:` line. A live acceptance record may describe product behavior and aggregate outcomes only after personal names, message subjects, account identifiers, provider relationships, tokens, and exact mailbox measurements have been removed or generalized.

This automated check is a guardrail, not proof that content is synthetic. Contributors must still review new fixtures and screenshots before committing them.
