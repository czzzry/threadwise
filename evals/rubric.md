# Email Eval Rubric

This is a simple v1 eval for two questions:

1. Did the agent assign the right label?
2. Did the agent correctly surface emails that need attention?

## Dataset contract

Each CSV row represents one email and includes:

- `expected_label`
- `expected_attention_required`

The eval runner asks the classifier to return:

- `label`
- `attention_required`
- `suggested_action`

## Metric definitions

### Label accuracy

`correct labels / total rows`

This is the simplest measure of whether the classifier maps emails into the right bucket.

### Attention-required recall

`true positives / all emails that actually required attention`

This matters because missing an actually important email is usually worse than over-surfacing one.

### False-ignore count

Count rows where:

- `expected_attention_required = true`
- predicted `attention_required = false`

This is the most important raw error count in the v1 sheet.

### Unsafe-action count

Count rows where:

- `expected_attention_required = true`
- classifier suggests an unsafe action such as `ignore`, `archive`, or `auto_handle`

This is a guardrail metric. Even if the label is correct, a dangerous action suggestion should still count against the system.

## How to interpret v1

- Good label accuracy with poor attention recall means the taxonomy is fine but the urgency logic is weak.
- Good attention recall with many false-ignore or unsafe-action errors means the action policy is still not trustworthy.
- This eval is intentionally small and readable. It is for learning and iteration, not for claiming benchmark-quality measurement.
