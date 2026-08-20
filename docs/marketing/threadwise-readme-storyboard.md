# Threadwise README Storyboard

**Status:** Visual proposal for founder approval  
**Current as of:** 2026-08-20  
**Implementation state:** The images are quality-bar stills. The repository README has not been redesigned yet.

## Creative Direction

Threadwise should look like a quiet layer inside an inbox, not another email client. The visual story begins with a wide, calm inbox and the small Threadwise mark. The panel appears only when human judgment is useful, stays level with the host interface, explains one narrow decision, advances immediately, and ends by proving that the same interaction exists in Gmail and Proton Mail.

The sequence deliberately avoids perspective tilt, floating dashboards, oversized app chrome, novelty cursors, and marketing scenes in which Threadwise obscures the inbox.

## Proposed README Opening

### Headline

**Your inbox, quietly sorted.**

### Supporting Copy

Threadwise labels routine mail in the background. When your judgment matters, open the same focused companion in Gmail or Proton Mail, make one decision, and move on.

### Primary Links

- Try the synthetic demo
- See how Threadwise works
- Install locally

### Hero Image

Use `docs/assets/marketing/readme-storyboard/01-quiet-inbox.png` at full README width. The first impression is the inbox, with Threadwise minimized to one small mark in the upper-right corner.

## Story Sequence

### 1. Quiet By Default

Use `01-quiet-inbox.png`.

Message: Threadwise is present without asking the user to work in another inbox or dashboard.

### 2. Routine Mail Is Already Handled

Use `02-background-labeling.png`.

Message: familiar mail receives labels in place while the one message needing judgment remains clearly distinguishable.

### 3. Open Only When Judgment Matters

Use `03-open-on-demand.png`.

Message: the companion opens beside the selected message. The inbox remains visible, the suggested labels are obvious, and the rationale is specific to this email.

### 4. One Decision, Then Next

Use `04-decision-to-next.png`.

Message: one clear action advances immediately. Provider writes finish in the background and return a visible receipt without blocking review.

### 5. The Same Threadwise In Both Inboxes

Use `06-provider-parity.png`.

Message: Gmail and Proton Mail retain their identity, while Threadwise's interaction, reasoning, controls, and terminology remain the same.

## Proposed README Order

1. Refined Threadwise mark, headline, supporting copy, and three links.
2. Wide quiet-inbox hero image.
3. A short three-part promise: labels in place, asks only when needed, works in Gmail and Proton Mail.
4. The four-image product story above.
5. A concise "What it does today" section with only user-facing capabilities.
6. A compact trust section covering local-first state, explicit provider writes, and synthetic public data.
7. Installation and local demo instructions.
8. Technical architecture, repository guide, project documents, and safety detail.

## What Changes From The Current README

- Replace the large legacy wordmark and technical opening with the refined mark, a literal product promise, and a wide product image.
- Move the link-heavy project-document list below the product story.
- Replace the early architecture explanation with a visual demonstration of the actual inbox workflow.
- Consolidate overlapping "What the demos show," "What it does today," and "Why it exists" copy into one short capability section.
- Keep the architecture diagram, safety boundaries, repository guide, local commands, and private-data policy, but place them after the reader understands the product.
- Use the same synthetic message examples throughout so the visual narrative does not feel assembled from unrelated demos.

## Motion After Approval

The eventual website animation should use these same compositions: wide inbox, a level push-in toward the Threadwise mark, panel open, one click, immediate next email, and return to the minimized mark. The camera remains level throughout. The GitHub README should retain strong static PNGs so it loads predictably; motion can be a lightweight optional enhancement rather than the only way to understand the product.
