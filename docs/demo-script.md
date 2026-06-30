# Threadwise MVP+1 Demo Script

Status: Current demo script for issue 070
Current as of: 2026-06-30
Builds on: `docs/prd.md`, `docs/issues/068-mvp-plus-one-design-review-and-aesthetic-direction.md`

This script defines the deterministic capture plan for the recruiter-facing Threadwise MVP+1 demo. Capture must use a Gmail test account populated only with synthetic messages. Do not show private email, credentials, OAuth screens, account settings, real unsubscribe execution, delete, trash, archive, send, or reply actions.

The approved visual direction is warm ink-and-paper Threadwise inside the real Gmail surface. The product story is Gmail-first; any ProtonMail or Outlook/Hotmail visual is roadmap-only.

## Output Assets

| Asset | Target file | Length | Purpose |
| --- | --- | ---: | --- |
| Daily briefing/report | `docs/assets/threadwise-daily-briefing.gif` | 10-20s | Show categorized Gmail and what Threadwise handled today. |
| Teach safely | `docs/assets/threadwise-teach-safely.gif` | 10-20s | Show selected email context, correction, impact preview, and explicit human choice. |
| Unsubscribe with approval | `docs/assets/threadwise-unsubscribe-approval.gif` | 10-20s | Show unsubscribe candidates and approval/review behavior without implying autonomy. |
| Roadmap micro-clip | `docs/assets/threadwise-roadmap-next.gif` | 6-10s | Optional. Show future inbox expansion, labeled as roadmap/next. |

Recommended static screenshots after GIF capture:

- `docs/assets/threadwise-daily-dashboard.png`
- `docs/assets/threadwise-teach-preview.png`
- `docs/assets/threadwise-unsubscribe-review.png`

## Global Capture Rules

- Browser viewport: desktop, 1440 x 900 preferred.
- Gmail account: test/demo account only, with a visible `Demo account` or equivalent marker when possible.
- Visible Gmail data: only the synthetic seed messages below.
- Overlay style: short warm ink-and-paper captions, bottom-left or top-left, never covering selected-email text or primary actions.
- Caption text: use the exact captions in this document unless the UI implementation makes a small wording adjustment necessary.
- Motion: slow cursor movement, one decision per clip, no frantic scrolling.
- Audio: none required; captions must stand alone.
- Current-scope disclaimer for README or first asset caption:
  - `Demo uses a Gmail test account populated with synthetic emails. No private inbox data is shown.`

## Flow 1: Daily Briefing / Report

Goal: A recruiter understands in under 20 seconds that Threadwise reads a Gmail inbox, categorizes mail, handles low-risk noise, and summarizes what happened today.

Starting state:

- Gmail inbox visible with synthetic messages.
- Threadwise sidebar open on the daily summary or selected-email state.
- Daily dashboard/report is available from the sidebar.

Timeline:

| Time | Action | Visible state | Caption |
| --- | --- | --- | --- |
| 0-3s | Open on Gmail inbox with Threadwise sidebar already loaded. | Synthetic inbox rows show a mix of work, receipts, newsletter, promotions, and low-value mail. | `Threadwise runs inside Gmail, using synthetic demo mail.` |
| 3-7s | Hover or briefly point at the sidebar `Today` summary. | Counts are visible: processed, auto-handled, need attention, unsubscribe candidates. | `Daily briefing: what arrived, what was labeled, and what still needs attention.` |
| 7-13s | Click the daily dashboard/report handoff. | Dashboard/report shows category breakdown and a short list of unresolved or attention-needed items. | `Low-risk categories are handled; uncertain items stay visible.` |
| 13-18s | Pause on the report summary. | Gmail-first scope and safety language remain visible or implied by captions. | `Current demo scope: Gmail-first, supervised, synthetic data.` |

Must show:

- Categorized email.
- What happened today.
- A small unresolved/needs-attention set.
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
| 0-3s | Select or start on the RoleScout Jobs email. | Sidebar shows sender, subject, current label, and short rationale. | `Threadwise explains the selected email decision.` |
| 3-7s | Click `Correct / Teach`. | Correction route appears: `Promotions -> Work` or `promotions -> job-related`. | `Corrections happen in context, next to the email.` |
| 7-12s | Show broader-impact preview. | Preview says the learned rule affects matching RoleScout job recommendation emails. | `Broader changes require approval before they apply.` |
| 12-17s | Choose the safest visible option, preferably `Use for future only`. | Acknowledgment confirms the rule is saved for future mail without rewriting existing messages. | `Human choice controls whether learning stays future-only or updates matches.` |

Preferred visible copy:

- Current decision: `Filed as Promotions`
- Correction: `Promotions -> Work`
- Learning summary: `RoleScout job recommendations should be treated as work-adjacent.`
- Impact preview: `4 matching emails`
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
| 0-4s | Open on the daily summary showing unsubscribe candidates. | `3 unsubscribe` or equivalent count is visible. | `Threadwise finds cleanup opportunities during the daily run.` |
| 4-9s | Open the unsubscribe review/handoff surface. | Candidates are grouped by sender/list with category and rationale. | `Unsubscribe stays in a review queue.` |
| 9-14s | Select one safe synthetic candidate, such as `Daily Deals Outlet`. | Approval UI shows candidate details and supported/manual status. | `The user chooses what to approve; unsupported cases stay manual.` |
| 14-18s | Stop before final external execution, or show a clearly simulated/test-account approval state only. | Audit/review state is visible without real-world unsubscribe execution. | `No autonomous unsubscribe in the public demo.` |

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
| 0-3s | Show Gmail as the current shipped demo surface. | Gmail card or icon is marked `Current demo`. | `Roadmap: Gmail-first today.` |
| 3-6s | Animate or reveal ProtonMail as next provider. | ProtonMail is marked `Read-only path exists / next product expansion`. | `Next: bring the same supervised loop to ProtonMail.` |
| 6-9s | Reveal Outlook/Hotmail as later direction. | Outlook/Hotmail is marked `Later`. | `Later: inbox-agnostic, still human-approved.` |

Do not claim:

- Multi-inbox aggregation is shipped.
- ProtonMail write-side behavior is shipped.
- Outlook/Hotmail integration is implemented.

## Synthetic Gmail Seed Plan

Seed only a test Gmail account. The messages below are fake and intentionally non-sensitive. Use controlled sender display names and domains such as `example.test`, `example.invalid`, or a test sender account. Avoid real people, real employers, real financial institutions, real order IDs, real addresses, and real unsubscribe links.

Target daily summary for capture:

- `24 processed`
- `14 auto-handled`
- `4 need attention`
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
  - `Daily briefing: categorized, handled, and needs-attention mail in one view.`
  - `Low-risk cleanup is bounded; uncertain mail stays visible.`
- Teach safely:
  - `Correct the agent next to the selected email.`
  - `Threadwise previews broader impact before changing matching mail.`
  - `The human chooses: future-only, apply to matches, or keep discussing.`
- Unsubscribe:
  - `Unsubscribe candidates are found during the daily run.`
  - `Cleanup stays in a review queue.`
  - `Approval is explicit; unsupported cases remain manual.`
- Roadmap:
  - `Roadmap: Gmail-first today.`
  - `Next: extend the same supervised loop beyond Gmail.`
  - `Later providers are direction, not shipped scope.`

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
