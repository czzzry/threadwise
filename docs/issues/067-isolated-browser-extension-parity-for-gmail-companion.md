# Status

Current
Current as of: 2026-06-29
Triage state: `ready-for-agent`
Builds on: `docs/issues/066-gmail-release-hardening-and-acceptance.md`, `docs/handoff/2026-06-29-live-gmail-acceptance-harness-and-trusted-types-hardening.md`

# Title

Make the isolated Gmail automation browser load the unpacked companion extension without host-driven injection

## Type

Chore

## User stories covered

`36`, `38`

## What to build

The supervised Gmail release is usable now, but the deterministic automation browser still relies on host-driven sidebar injection and host-driven message fulfillment during live acceptance.

That is good enough for acceptance and debugging, but it is not full parity with the normal installed-extension path.

This slice should narrow that gap:

- make the isolated Chrome automation profile load the unpacked Gmail companion extension reliably
- ensure the content script and background path start cleanly without host-side reinjection
- keep the direct CDP acceptance harness as a verification tool, but stop requiring it to impersonate the extension runtime

## Acceptance criteria

- [ ] The isolated automation Chrome profile loads the unpacked extension reliably on startup.
- [ ] The Gmail companion sidebar appears in the live Gmail page without host-driven reinjection.
- [ ] The extension background/content message path works in the isolated automation browser without host-side message emulation.
- [ ] The existing direct CDP acceptance harness can validate the live Gmail page while relying on the real extension path instead of a fallback shim.

## Output

- isolated-browser extension-loading parity for Gmail companion acceptance
- reduced gap between deterministic automation runs and the founder's normal installed-extension path
