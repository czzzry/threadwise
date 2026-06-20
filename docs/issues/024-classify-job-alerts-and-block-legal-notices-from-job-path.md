# Title

Classify job alerts and block legal notices from the job path

## Type

HITL

## User-visible goal

Reduce manual review on repeated job-alert messages while preventing obvious non-job legal notices from being mislabeled as work that needs a response.

## Scope

- Tighten the local classifier only
- Classify LinkedIn job-alert style messages into `job-related`
- Preserve the existing behavior that LinkedIn direct-message digests can still surface `personal`
- Prevent legal or class-action notice emails from falling into the `reply-needed` plus `job-related` path

## Non-goals

- Broad employment-mail classification beyond the repeated job-alert pattern
- New labels or taxonomy expansion
- Gmail mutation behavior changes
- General handling for every type of legal or administrative notice

## Acceptance criteria

- LinkedIn job alerts like `GTM Engineer at FactFinder` surface `EA/JobRelated`
- LinkedIn direct-message digests like `Kirth just messaged you` still surface `EA/Personal`
- Legal notice emails such as class-action settlement notices do not surface `EA/JobRelated`
- Existing job-application pipeline mail continues to surface `EA/JobRelated`

## Expected tests or verification

- Test LinkedIn job alerts classify to `job-related`
- Test LinkedIn direct-message digests still classify to `personal`
- Test class-action settlement notices do not classify to `reply-needed` plus `job-related`
- Re-run the relevant classifier, stored-batch, fetcher, and local-browser suites
