# Email Eval v1

This is a very small, readable eval suite for the email classification agent.

It measures:

- label accuracy
- attention-required recall
- false-ignore count
- unsafe-action count

## Files

- `email_eval_dataset.csv`: 10 sample emails
- `rubric.md`: metric definitions
- `run_email_eval.py`: simple eval runner
- `results.csv`: generated output

## How to run

From the repo root:

```bash
python3 evals/run_email_eval.py
```

That will:

1. load the sample dataset
2. run the classifier function on each row
3. write per-row results to `evals/results.csv`
4. print summary metrics in the terminal

## Where to plug in the real classifier

Open:

- `evals/run_email_eval.py`

Replace the body of:

- `classify_email(row)`

The function should return:

```python
{
    "label": "EA/Work",
    "attention_required": True,
    "suggested_action": "review",
}
```

For v1, the file uses a clearly marked stub classifier so the eval can run immediately without depending on the full production pipeline.

## Why this is intentionally simple

This is not a benchmark framework. It is a starter eval you can understand, edit, and grow over time as you connect more of the real system.
