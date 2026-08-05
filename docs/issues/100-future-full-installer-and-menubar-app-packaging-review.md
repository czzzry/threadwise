# Future full installer and menubar app packaging review

Status: Completed as a bounded personal menu-bar control on 2026-08-05
Type: HITL
GitHub issue: `#25`
Parent: GitHub issue `#16`; `docs/threadwise-startup-and-packaging-model-review-2026-07-01.md`

## What to build

After the personal startup loop has been used, review whether Threadwise should graduate to a full macOS installer, packaged helper, or menubar app.

Real use showed that Terminal-only service management was causing avoidable uncertainty. The approved implementation keeps the existing LaunchAgent and repo-local data model, adding only a native personal menu-bar control and installer.

## Acceptance criteria

- [x] Real use established that a menu-bar control adds value while retaining the current LaunchAgent path.
- [x] The personal control exposes unambiguous status plus safe Start and Stop actions.
- [x] Existing runtime configuration, data, and Proton Mail Bridge integration remain in place.
- [x] Repo-path dependence is acceptable for this personal installation and is explicit in the bundled control configuration.
- [x] Moving data, signing, notarization, and automatic updates remain deferred until distribution beyond this Mac is justified.

## Safety boundaries

- Keep installation personal and local; do not introduce distribution infrastructure.
- Do not move private local artifacts without explicit approval.

## Parallelization

Wait until `#22`, `#23`, and `#24` have been used enough to evaluate.
