# Threadwise MVP+1 Demo Script

Status: Historical capture script for completed issue 070
Historical context as of: 2026-06-30
Current demo entry points: [README.md](../README.md)
Builds on: `docs/prd.md`, `docs/issues/068-mvp-plus-one-design-review-and-aesthetic-direction.md`

This script preserves the deterministic capture plan for the recruiter-facing Threadwise MVP+1 recorded walkthrough. Capture must use a Gmail test account populated only with synthetic messages. Do not show private email, credentials, OAuth screens, account settings, real unsubscribe execution, delete, trash, archive, send, or reply actions.

The approved visual direction is warm ink-and-paper Threadwise inside the real Gmail surface. The product story is Gmail-first; any ProtonMail or Outlook/Hotmail visual is roadmap-only.

## Output Assets

| Asset | Target file | Length | Purpose |
| --- | --- | ---: | --- |
| Daily briefing/report | `docs/assets/threadwise-daily-briefing.gif` | 4-6s | Show categorized Gmail and what Threadwise handled today. |
| Teach safely | `docs/assets/threadwise-teach-safely.gif` | 4-6s | Show selected email context, correction, impact preview, and explicit human choice. |
| Unsubscribe with approval | `docs/assets/threadwise-unsubscribe-approval.gif` | 4-6s | Show unsubscribe candidates and approval/review behavior without implying autonomy. |
| Roadmap micro-clip | `docs/assets/threadwise-roadmap-next.gif` | 4-6s | Optional. Show future inbox expansion, labeled as roadmap/next. |

Recommended static screenshots after GIF capture:

- `docs/assets/threadwise-daily-dashboard.png`
- `docs/assets/threadwise-teach-preview.png`
- `docs/assets/threadwise-unsubscribe-review.png`

## Global Capture Rules

- Browser viewport: desktop, 1440 x 900 preferred.
- Gmail account: test/demo account only, with a visible `Demo account` or equivalent marker when possible.
- Visible Gmail data: only the synthetic seed messages below.
- Source of truth: use the approved final UI surfaces. If the stage file or capture route drifts from the live design, fix that before producing final assets.
- Overlay style: short warm ink-and-paper captions, bottom-left or top-left, never covering selected-email text or primary actions.
- Caption text: use the exact captions in this document unless the UI implementation makes a small wording adjustment necessary.
- Motion: short highlight transitions, one decision per clip, no frantic scrolling.
- Cursor visibility: avoid a large cursor overlay. If a click must be shown, use a small clean pointer or omit it.
- Typing visibility: when text is entered, the insertion caret should be visible before typing begins, and typed text should appear slowly enough to follow in a silent GIF.
- Text-entry rhythm: for teach/correction text, prefer a short scripted sentence typed at roughly 8-14 characters per second instead of pasting instantly.
- Audio: none required; captions must stand alone.
- Current-scope disclaimer for README or first asset caption:
  - `Demo uses a Gmail test account populated with synthetic emails. No private inbox data is shown.`

## Capture Order

Produce the first pass in this order:

1. Daily briefing / report GIF
2. Teach safely GIF
3. Unsubscribe approval GIF
4. Optional roadmap / next GIF
5. Static screenshots for README and portfolio placement
6. MP4 versions only after the GIFs are approved

If any clip reveals a layout mismatch, stop and fix the source surface before continuing the remaining clips.

## Flow 1: Daily Briefing / Report

Goal: A recruiter understands in under 6 seconds that Threadwise reads a Gmail inbox, categorizes mail, handles low-risk noise, and summarizes what happened today.

Starting state:

- Gmail inbox visible with synthetic messages.
- Threadwise sidebar open on the daily summary or selected-email state.
- Daily dashboard/report is available from the sidebar.

Timeline:

| Time | Action | Visible state | Caption |
| --- | --- | --- | --- |
| 0-1s | Open on Gmail inbox with Threadwise sidebar already loaded. | Synthetic inbox rows show a mix of work, receipts, newsletter, promotions, and low-value mail. | `Threadwise runs inside Gmail, using synthetic demo mail.` |
| 1-2s | Highlight the sidebar summary. | Counts are visible: processed, auto-handled, review needed, unsubscribe candidates. | `Daily run completed.` |
| 2-3s | Point to the uncertain-mail stat and explainer. | The review-needed count stays visible. | `Uncertain mail stays visible.` |
| 3-5s | Highlight the dashboard button, then cut to the dashboard view. | Dashboard/report shows category breakdown and a short list of unresolved items. | `Open the daily dashboard.` |

Must show:

- Categorized email.
- What happened today.
- A small unresolved/review-needed set.
- No private account information.

Do not show:

- OAuth consent screens.
- Real account names beyond the test Gmail account.
- Any delete, trash, archive, send, or reply action.

## Flow 2: Teach Safely

Goal: A recruiter sees the core human-in-the-loop product loop: selected email context, correction, impact preview, and explicit human choice before broader learning.

Starting state:

- Gmail inbox visible.
- Selected email: `RoleScout Jobs - Senior AI product roles this week`.
- Threadwise sidebar says the message was filed as `Promotions` or equivalent low-risk category but can be corrected to `EA/Work` / `job-related`.

Timeline:

| Time | Action | Visible state | Caption |
| --- | --- | --- | --- |
| 0-1s | Highlight the selected job email row. | The selected row is visible in the inbox list. | `A job email is selected.` |
| 1-2s | Highlight the selected email card. | Sidebar shows sender, subject, current label, and short rationale. | `Threadwise explains the decision.` |
| 2-3s | Highlight the `Correct / Teach` area. | The correction path is obvious next to the selected email. | `Teach: Promotions → EA/Work.` |
| 3-5s | Highlight preview. | Preview says the learned rule affects matching RoleScout job recommendation emails. | `Preview first. Nothing changes blindly.` |

Preferred visible copy:

- Current decision: `Filed as Promotions`
- Correction: `Promotions -> Work`
- Learning summary: `RoleScout job recommendations should be treated as work-adjacent.`
- Impact preview: `4 matching emails`
- Typed note: `RoleScout job alerts should be work.`
- Choices:
  - `Use for future only`
  - `Apply to 4`
  - `Keep discussing`

Must show:

- Selected-email context.
- Correction.
- Broader-impact preview.
- Explicit human choice before applying to other emails.

Do not show:

- Any claim that Threadwise learns globally without confirmation.
- Any application to private or real historical inbox data.

## Flow 3: Unsubscribe With Approval

Goal: A recruiter sees practical inbox cleanup while understanding that unsubscribe action is reviewed and approved, not autonomous.

Starting state:

- Gmail inbox visible with synthetic newsletter/promotional messages.
- Threadwise sidebar or dashboard shows `3 unsubscribe` candidates.

Timeline:

| Time | Action | Visible state | Caption |
| --- | --- | --- | --- |
| 0-1s | Highlight `Daily Deals Outlet` in the inbox list. | The synthetic promo row is selected. | `Daily Deals Outlet.` |
| 1-2s | Highlight the unsubscribe count. | `3 unsubscribe candidates` is visible. | `3 unsubscribe candidates.` |
| 2-3s | Highlight the explanatory note. | Nothing has been executed yet. | `Nothing has been executed.` |
| 3-5s | Highlight `Review unsubscribe candidates`. | The review queue is the next step. | `Review unsubscribe candidates.` |

Must show:

- Unsubscribe availability.
- Review/approval behavior.
- Manual or unsupported handling if relevant.
- Clear safety boundary.

Do not show:

- Clicking a real unsubscribe link.
- Sending a real unsubscribe email.
- Claiming unsupported lists are executed automatically.

## Optional Flow 4: Roadmap / Next Micro-Clip

Goal: Show the future inbox-agnostic direction without implying it has shipped.

Length: 6-10 seconds.

Label requirement: The first visible caption must include `Roadmap` or `Next`, and the visual must not sit beside the three primary GIFs as shipped behavior without the same label.

Timeline:

| Time | Action | Visible state | Caption |
| --- | --- | --- | --- |
| 0-1s | Highlight Gmail as the current shipped demo surface. | Gmail card is active. | `Current demo: Gmail.` |
| 1-2s | Highlight ProtonMail as next provider. | ProtonMail card is active. | `Next: same supervised loop.` |
| 2-3s | Highlight Outlook/Hotmail as later direction. | Outlook/Hotmail card is active. | `Later: inbox-agnostic.` |
| 3-5s | Hold on the three-card view. | All three cards remain visible. | `Gmail-first today. Inbox-agnostic later.` |

Do not claim:

- Multi-inbox aggregation is shipped.
- ProtonMail write-side behavior is shipped.
- Outlook/Hotmail integration is implemented.

## Synthetic Gmail Seed Plan

Seed only a test Gmail account. The messages below are fake and intentionally non-sensitive. Use controlled sender display names and domains such as `example.test`, `example.invalid`, or a test sender account. Avoid real people, real employers, real financial institutions, real order IDs, real addresses, and real unsubscribe links.

Target daily summary for capture:

- `24 processed`
- `14 auto-handled`
- `4 review needed`
- `3 unsubscribe candidates`
- `1 unsupported/manual unsubscribe follow-up`

| ID | Sender display | Sender email | Subject | Snippet | Intended category | Demo role |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | RoleScout Jobs | jobs@example.test | Senior AI product roles this week | New recommendations based on your profile and saved searches. | `promotions` initially, corrected to `job-related` / `EA/Work` | Teach flow selected email. |
| S02 | RoleScout Jobs | jobs@example.test | Product engineer openings near Berlin | Six new roles match your saved search. | `promotions` initially, matching `job-related` preview | Teach impact match. |
| S03 | RoleScout Jobs | jobs@example.test | AI product manager roles hiring now | Hiring teams are reviewing candidates this week. | `promotions` initially, matching `job-related` preview | Teach impact match. |
| S04 | RoleScout Jobs | jobs@example.test | Startup product roles you may like | New roles from early-stage teams. | `promotions` initially, matching `job-related` preview | Teach impact match. |
| S05 | RoleScout Learning | learning@example.test | New course: building AI workflows | A short course on evaluating AI assistant behavior. | `newsletter` | Similar but not part of RoleScout Jobs correction. |
| S06 | Northstar Weekly | weekly@example.test | Five essays worth reading | A concise roundup for product builders. | `newsletter` | Daily briefing visible row; unsubscribe candidate. |
| S07 | Daily Deals Outlet | deals@example.test | Final hours: 40 percent off workspace gear | Your subscriber-only code expires tonight. | `promotions` | Unsubscribe candidate; approval example. |
| S08 | SaaS Webinar Club | events@example.test | Tomorrow: automate your inbox workshop | Reserve your place for the live session. | `promotions` | Unsubscribe candidate. |
| S09 | City Rail | receipts@example.test | Your trip receipt | Booking confirmation and travel details for tomorrow. | `travel` | Daily briefing category variety. |
| S10 | Cloud Billing | billing@example.test | Monthly invoice available | Your account statement is ready to view. | `receipt-billing` | Daily briefing category variety. |
| S11 | Dev Store | orders@example.test | Your keyboard order shipped | Tracking will update after the carrier scans the package. | `shopping-order` | Daily briefing category variety. |
| S12 | Calendar Bot | calendar@example.test | Coffee chat confirmed for Thursday | Calendar invitation details are attached. | `calendar-event` | Needs-attention example. |
| S13 | Repo Security | security@example.test | Security alert resolved | Dependency Bot closed one vulnerability in your repo. | `account-security` | High-importance non-cleanup mail. |
| S14 | Alex Rivera | alex@example.test | Quick note on the portfolio review | I left comments on the demo flow and can review again Friday. | `personal`, `reply-needed` | Needs-attention example. |
| S15 | Hiring Coordinator | hiring@example.test | Interview availability request | Could you share two times that work next week? | `job-related`, `reply-needed` | Needs-attention example. |
| S16 | Product Ops Forum | forum@example.test | Digest: 18 unread threads | Popular posts from this week's product ops forum. | `newsletter` | Non-urgent visible mail. |
| S17 | Account Notice | account@example.test | New sign-in to your demo account | A sign-in was detected from your current browser. | `account-security` | Safe account-security example; no real details. |
| S18 | Utopia Offers | offers@example.test | Utopia Age 113 is almost here | An intentionally low-value novelty promotion. | `spam-low-value` | Auto-handled low-value example. |
| S19 | Promo Arcade | arcade@example.test | Spin for mystery rewards | You have bonus spins waiting. | `spam-low-value` | Auto-handled low-value example. |
| S20 | Receipts Desk | receipts@example.test | Receipt for workspace subscription | Your demo subscription receipt is ready. | `receipt-billing` | Daily report count filler. |
| S21 | Travel Desk | travel@example.test | Gate change for sample itinerary | Your demo flight now departs from Gate B12. | `travel` | Daily report count filler. |
| S22 | Newsletter Lab | newsletter@example.test | This week in practical AI | Three links on evaluation, UX, and safety. | `newsletter` | Optional unsubscribe/manual contrast. |
| S23 | Project Partner | partner@example.test | Can you approve the demo copy? | Please confirm the wording before the capture pass. | `reply-needed` | Needs-attention example. |
| S24 | Platform Updates | updates@example.test | Terms update for demo workspace | Review the updated workspace terms when convenient. | `unlabeled` or `account-security` | Safe unresolved/taxonomy-gap example. |

Seed body guidance:

- Keep bodies one to three short paragraphs.
- Include no addresses, phone numbers, legal threats, medical content, financial account numbers, credentials, real receipts, or real personal history.
- For unsubscribe candidates, use fake body text such as `Unsubscribe link: https://unsubscribe.example.invalid/daily-deals-outlet`.
- If the seeding method supports `List-Unsubscribe` headers, use only `.invalid` or `.test` URLs/mailboxes controlled for the demo. Do not use real marketing lists.
- Keep `RoleScout Jobs` as a fictional display name for demo clarity; do not seed with real recruiting-platform emails or real job postings.

## Caption Set

Use these as overlay captions or README captions.

- Daily briefing:
  - `Threadwise runs inside Gmail, using synthetic demo mail.`
- `Daily run completed.`
- `Uncertain mail stays visible.`
- Teach safely:
- `A job email is selected.`
- `Threadwise explains the decision.`
- `Preview first. Nothing changes blindly.`
- Unsubscribe:
- `Daily Deals Outlet.`
- `Nothing has been executed.`
- `Review unsubscribe candidates.`
- Roadmap:
- `Current demo: Gmail.`
- `Next: same supervised loop.`
- `Later: inbox-agnostic.`

## Capture Safety Checklist

Before capture:

- [ ] Confirm the browser profile is logged into the test Gmail account only.
- [ ] Confirm the visible inbox contains only the synthetic seed messages above.
- [ ] Confirm no private email, private account avatar, account switcher, OAuth screen, credential, recovery email, phone number, or browser password UI is visible.
- [ ] Confirm no real sender, real employer, real customer, real financial institution, real unsubscribe list, or real order identifier appears in visible text.
- [ ] Confirm the roadmap clip is labeled `Roadmap` or `Next` before any non-Gmail provider appears.
- [ ] Confirm the clip copy does not claim multi-inbox support as shipped.

During capture:

- [ ] Do not click delete, trash, archive, send, reply, report spam, account settings, or OAuth controls.
- [ ] Do not execute a real unsubscribe. Stop at review/approval state, or use only a clearly safe test-account simulation.
- [ ] Do not expose browser extensions, devtools, terminal windows, local filesystem paths, API keys, cookies, or tokens.
- [ ] Keep captions away from selected email content and primary safety decisions.

After capture:

- [ ] Review every frame for private data and account-identifying UI.
- [ ] Verify captions are readable at README size.
- [ ] Verify GIF filenames match the planned `docs/assets/` names.
- [ ] Verify the first README mention says the demo uses synthetic Gmail data.
- [ ] Verify final assets do not imply delete, broad archive, autonomous unsubscribe, send/reply automation, shipped ProtonMail mutation, or shipped Outlook/Hotmail support.
