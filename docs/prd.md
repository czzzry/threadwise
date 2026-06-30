# PRD

Status: Current bounded-slice PRD
Current as of: 2026-06-30
Builds on: `docs/mvp-plus-one-portfolio-demo-alignment.md`, `docs/portfolio.md`, `docs/checkpoints/current-operating-model-2026-06-22.md`
Supersedes as current planning focus: `docs/archive/prd-gmail-inbox-companion-release-completed-2026-06-30.md`
Release target: recruiter-ready Threadwise portfolio demo
Product target after this: product expansion planning, including inbox-agnostic / multi-inbox direction

This PRD describes the MVP+1 portfolio-demo release slice.

## Problem Statement

Threadwise now has a working Gmail-first supervised product surface:

- Gmail daily triage with bounded provider-side write-back
- limited `INBOX` removal for approved low-value categories
- a browser-based Gmail companion sidebar
- selected-email classification and short rationale
- in-context `Correct / Teach`
- broader-impact preview before multi-email changes
- compact daily summary, fuller daily dashboard, and unsubscribe review handoff

That is enough for a real MVP, but it is not yet enough for a recruiter or hiring manager to understand the project quickly.

The current repo still asks too much of a reviewer:

- they have to read several docs to understand the product story
- the README does not yet show polished demo assets at the top
- the strongest product loop is not visible without setup
- the UI was built for proving behavior, not for portfolio-grade capture
- public screenshots and video/GIF assets are still missing
- the next-phase story can drift between ProtonMail expansion, backend capability, and portfolio packaging unless it is explicitly bounded

The founder wants MVP+1 to make Threadwise marketable as a portfolio project for an AI product engineer / product-minded full-stack builder.

The next problem is:

> Can we turn the completed Gmail MVP into a polished, recruiter-readable portfolio artifact that shows the human-in-the-loop AI product loop in under a minute, without exposing private email or overclaiming product scope?

## Solution

Build a recruiter-ready demo and repo packaging pass around the existing Gmail-first product.

The MVP+1 release should:

- run the public demo through real Gmail UI using a Gmail test account seeded only with synthetic emails
- polish the Threadwise sidebar, daily dashboard, teach flow, and unsubscribe review surfaces before capture
- define and apply a coherent visual aesthetic for portfolio-quality screenshots/video
- produce short GIF/video assets that communicate the product loop without requiring local setup
- update the README and portfolio docs so the first screen explains Threadwise quickly
- keep the deeper technical story available below the fold for hiring managers
- clearly label synthetic demo data and roadmap content
- keep the existing safety boundaries intact

The first major phase is a design review:

- audit the current capture surfaces
- identify what can be changed visually in the Threadwise-controlled UI
- identify what remains constrained by Gmail
- propose 2-3 aesthetic directions
- select one direction
- implement it before writing the final capture script

The working aesthetic direction to explore first is:

> Calm AI operator.

The product should feel calm, precise, and credible inside Gmail: compact but premium information density, restrained color, strong hierarchy, readable status pills, clear impact-preview panels, and obvious confirmation choices.

## User Stories

1. As a recruiter, I want the README to show what Threadwise does before I run anything, so that I can understand the project quickly.
2. As a recruiter, I want a short GIF/video at the top of the README, so that I can see the product loop without installing dependencies.
3. As a recruiter, I want the demo to use real Gmail UI, so that the project feels credible and not like a fake email toy.
4. As a recruiter, I want the demo data to be clearly synthetic, so that I know private email is not being exposed.
5. As a recruiter, I want the first visual to show categorized email and a daily briefing, so that I immediately understand the value proposition.
6. As a recruiter, I want a second visual to show `Correct / Teach`, so that I understand the human-in-the-loop AI interaction.
7. As a recruiter, I want the teach demo to show broader-impact preview, so that I see the safety model is deliberate.
8. As a recruiter, I want a third visual to show unsubscribe approval, so that I see Threadwise can handle practical inbox cleanup safely.
9. As a recruiter, I want small overlay captions, so that the demo explains itself even if I skim silently.
10. As a recruiter, I want static screenshots below the GIFs, so that I can inspect the UI at my own pace.
11. As a recruiter, I want the README to say what the founder built or directed, so that I can evaluate the candidate clearly.
12. As a recruiter, I want the README to distinguish current behavior from roadmap, so that the project does not feel inflated.
13. As a recruiter, I want the repo to look organized and intentional, so that I trust the work before digging into code.
14. As a hiring manager, I want technical depth one click deeper, so that I can inspect architecture after the product hook lands.
15. As a hiring manager, I want to understand the safety boundaries, so that I can see the product judgment behind the automation.
16. As a hiring manager, I want to see that the Gmail companion is backed by tests and acceptance harnesses, so that the demo is not only a mockup.
17. As a hiring manager, I want the implementation docs to separate historical planning from current scope, so that I can follow the engineering process.
18. As a hiring manager, I want the demo to show behavior already implemented in the repo, so that the portfolio does not misrepresent capabilities.
19. As a hiring manager, I want the demo route or capture path to be deterministic, so that reviewers can reproduce or update the assets later.
20. As a hiring manager, I want the UI states to be polished but plausible, so that the product feels real rather than like a marketing-only facade.
21. As the founder, I want the sidebar to look more intentional, so that screenshots communicate product taste as well as functionality.
22. As the founder, I want to know how far the sidebar can visually change, so that design work stays realistic inside Gmail.
23. As the founder, I want the design review to call out Gmail constraints, so that we do not waste time trying to redesign Gmail itself.
24. As the founder, I want 2-3 aesthetic directions before implementation, so that the visual direction is chosen deliberately.
25. As the founder, I want the selected aesthetic incorporated into the real Threadwise UI, so that demo assets come from the product surface.
26. As the founder, I want the UI to be a little slicker for portfolio capture, so that the project competes visually without lying.
27. As the founder, I want the daily briefing demo to be 10-20 seconds max, so that the README stays easy to skim.
28. As the founder, I want the teach flow demo to be 10-20 seconds max, so that the core safety loop is concise.
29. As the founder, I want the unsubscribe demo to be 10-20 seconds max, so that the cleanup feature is visible without bloating the README.
30. As the founder, I want an optional roadmap micro-clip, so that the multi-inbox / inbox-agnostic direction is visible as "next" rather than current scope.
31. As the founder, I want the roadmap clip to show Gmail to ProtonMail to Outlook/Hotmail, so that the future product direction is obvious.
32. As the founder, I want roadmap visuals clearly labeled as future, so that reviewers do not confuse them with shipped behavior.
33. As the founder, I want the demo Gmail account seeded with synthetic emails, so that capture does not expose private data.
34. As the founder, I want synthetic emails chosen for demo clarity, so that categories and corrections are easy to understand.
35. As the founder, I want sensitive areas avoided in demo data, so that the portfolio does not create privacy or reputational risk.
36. As the founder, I want the README to include a demo disclaimer, so that the synthetic-data setup is transparent.
37. As the founder, I want the public assets committed under `docs/assets/`, so that the README works on GitHub without local setup.
38. As the founder, I want optional MP4 versions, so that higher-quality demo embeds or portfolio pages can use them later.
39. As the founder, I want the interactive/local demo path to remain secondary, so that recruiters are not forced to run scripts.
40. As the founder, I want the final MVP+1 closeout to include a clean git state, so that the public repo is publishable.
41. As a future agent, I want the PRD to define capture surfaces and constraints, so that implementation does not drift into backend expansion.
42. As a future agent, I want the first slice to be design review, so that screenshots are not captured from a rough UI.
43. As a future agent, I want demo assets to be generated from deterministic flows, so that updates do not depend on ad hoc manual clicking.
44. As a future agent, I want acceptance criteria for visual polish, so that "looks good" becomes reviewable.
45. As a future agent, I want current docs updated after the demo pass, so that the repo stops saying screenshots are missing once they exist.

## Implementation Decisions

- MVP+1 is portfolio packaging, not provider expansion.
- The immediate release target is a recruiter-ready Threadwise demo and README/portfolio refresh.
- The demo should use real Gmail UI with a test Gmail account seeded only with synthetic emails.
- The demo should not use private founder email, production credentials, or sensitive inbox content.
- The demo may use overlay captions, but captions must not claim behavior that is not implemented.
- The README should prioritize visual clarity first:
  - one-line product pitch
  - prominent Threadwise logo treatment
  - short GIF/video assets near the top
  - concise synthetic-data disclaimer
  - static screenshots
  - deeper architecture and safety details lower down
- The founder-provided Threadwise logo direction should be used as the brand source for MVP+1:
  - use the square app icon in product/demo UI where space is tight
  - use the primary logo and tagline in README, portfolio, and promo assets
  - extract separate public assets from the current logo sheet before final packaging
- The demo assets should include three short primary flows:
  - daily briefing/report
  - teach the agent safely
  - unsubscribe with approval
- The demo may include one roadmap micro-clip showing Gmail to ProtonMail to Outlook/Hotmail, but it must be labeled as "Next" or "Roadmap."
- The first implementation phase should be design review and aesthetic direction before capture scripting.
- The design review should define:
  - current UI strengths and weaknesses
  - visual-change boundaries inside Gmail
  - 2-3 aesthetic options
  - recommended direction
  - concrete implementation checklist
- The initial aesthetic to explore is "Calm AI operator."
- The chosen aesthetic should be incorporated into Threadwise-controlled surfaces:
  - Gmail companion sidebar
  - daily dashboard
  - teach/impact preview state
  - unsubscribe review/handoff state
  - demo overlay captions
  - Threadwise app icon and brand treatments
- The UI may be slightly more polished for portfolio capture than the raw internal product, but it must remain truthful to implemented behavior.
- The interactive/local demo path should be secondary to committed README assets.
- Public assets should be committed under `docs/assets/`.
- Historical Gmail release planning should stay archived and linkable, but no longer drive the current PRD.
- The product safety boundaries remain unchanged:
  - no delete, trash, broad archive, send, or reply automation
  - no real unsubscribe execution in a public demo without explicit test-account safety
  - no private email content in public artifacts
  - no provider-side ProtonMail mutation

## Testing Decisions

- Good tests should prove portfolio/demo behavior at the highest practical seam, not internal helper details.
- Existing tests for the Gmail companion UI should continue to cover user-visible sidebar, dashboard, teach, and unsubscribe behavior.
- Design implementation should preserve or expand tests around:
  - sidebar selected-email rendering
  - teach preview and confirmation copy
  - daily dashboard route
  - unsubscribe review handoff
  - simulator/demo rendering where used
- Visual capture should be validated with browser screenshots before recording final assets.
- If a deterministic demo route or capture script is added, it should have a smoke test proving:
  - the route loads
  - required demo states exist
  - no private data fixtures are referenced
  - the capture viewport does not produce obvious overflow or clipped text
- README asset references should be checked so committed GIFs/screenshots render through relative GitHub paths.
- Demo copy should be reviewed against actual implemented behavior to avoid overclaiming.
- If a real Gmail test account is used for capture, the capture checklist should confirm:
  - only synthetic emails are visible
  - no credentials or private account information appear in assets
  - unsafe actions are simulated or explicitly bounded to the test account

## Out of Scope

- Adding ProtonMail write-side behavior.
- Shipping multi-inbox aggregation as part of this phase.
- Building a generic provider platform.
- Adding new autonomous inbox actions.
- Deleting, trashing, broadly archiving, sending, or replying to email.
- Making recruiters run a local server before seeing the product story.
- Redesigning Gmail itself.
- Using private founder email in public screenshots or videos.
- Capturing demo assets before the design review/aesthetic pass.
- Treating the roadmap micro-clip as current shipped functionality.

## Further Notes

- This PRD intentionally moves MVP+1 away from backend expansion and toward portfolio packaging.
- Product expansion to ProtonMail and inbox-agnostic workflows remains valuable, but it should follow the recruiter-ready demo pass.
- The next slice should be design review and aesthetic direction, not GIF capture.
- The final MVP+1 closeout should include committed assets, README/portfolio updates, tests/smokes, clean `git status`, push, and optional milestone tag.
