# Threadwise Demo Capture Notes

Status: Generated asset notes
Current as of: 2026-06-30
Builds on: `docs/demo-script.md`, `docs/issues/071-capture-recruiter-ready-demo-assets.md`

Generated assets:

- `docs/assets/threadwise-daily-briefing.gif`
- `docs/assets/threadwise-teach-safely.gif`
- `docs/assets/threadwise-unsubscribe-approval.gif`
- `docs/assets/threadwise-roadmap-next.gif`
- `docs/assets/threadwise-daily-dashboard.png`
- `docs/assets/threadwise-teach-preview.png`
- `docs/assets/threadwise-unsubscribe-review.png`
- `docs/assets/threadwise-roadmap-next.png`
- MP4 versions are pending GIF approval.

Capture method:

- deterministic synthetic capture stage: `docs/assets/demo-stage/threadwise-demo-stage.html`
- Chrome DevTools screenshots at `8` fps
- GIF encoding via `ffmpeg`
- MP4 encoding via `ffmpeg` when `--include-mp4` is passed
- output viewport: `1280x800`
- GIF scale: `960px` wide

Safety:

- all visible emails, senders, domains, and account labels are synthetic demo data
- no private inbox, credentials, OAuth screen, account settings, delete, archive, send, reply, or real unsubscribe execution is shown
- roadmap asset is explicitly labeled as future direction, not shipped behavior

Review notes:

- first pass intentionally uses a controlled Gmail-like synthetic stage so cursor movement, zooms, captions, and typing/caret visibility are deterministic
- MP4 generation is gated behind `--include-mp4` so the founder can approve the GIF direction before long-form exports are produced
- final README placement can choose GIF or MP4 depending on GitHub rendering and file size