# Status

Implemented on 2026-06-23
Current as of: 2026-06-23
Triage state: `implemented`
Builds on: `/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/prd.md`
Blocked by: None

# Title

Classify Trainline trip updates as travel

## Type

AFK

## User-visible goal

Reduce a recurring reviewed unlabeled Gmail exception family by classifying Trainline trip updates like `Your train is delayed` and `Get ready for …` into `travel`.

## Scope

- Tighten the local classifier only
- Cover recurring Trainline travel-update patterns already seen in stored batches
- Keep the slice inside the existing `travel` taxonomy
- Preserve current handling for more general bulk-update and promo messages

## Non-goals

- Broader travel-message redesign
- New labels or taxonomy expansion
- Gmail mutation behavior changes
- Solving every remaining unlabeled sender family

## Acceptance criteria

- Trainline `Your train is delayed` messages classify to `travel`.
- Trainline `Get ready for …` trip-reminder messages classify to `travel`.
- The slice does not broaden Gmail mutation scope.

## Expected tests or verification

- Add classifier tests for the recurring Trainline delay and trip-readiness patterns.
- Re-run the classifier suite.
- Re-run the current-gap analysis and confirm the Trainline family no longer remains unlabeled under the current classifier.
