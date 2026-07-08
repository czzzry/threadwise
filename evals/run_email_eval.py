from __future__ import annotations

import csv
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVALS_DIR / "email_eval_dataset.csv"
RESULTS_PATH = EVALS_DIR / "results.csv"

UNSAFE_ACTIONS = {"ignore", "archive", "auto_handle"}


def main() -> int:
    rows = load_dataset(DATASET_PATH)
    results = [evaluate_row(row) for row in rows]
    metrics = compute_metrics(results)
    write_results(RESULTS_PATH, results, metrics)

    print("Email eval complete")
    print(f"- dataset: {DATASET_PATH}")
    print(f"- results: {RESULTS_PATH}")
    print(f"- label accuracy: {metrics['label_accuracy']:.2%}")
    print(f"- attention-required recall: {metrics['attention_required_recall']:.2%}")
    print(f"- false-ignore count: {metrics['false_ignore_count']}")
    print(f"- unsafe-action count: {metrics['unsafe_action_count']}")
    return 0


def load_dataset(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def evaluate_row(row: dict[str, str]) -> dict[str, str]:
    prediction = classify_email(row)
    expected_attention = parse_bool(row["expected_attention_required"])
    predicted_attention = bool(prediction["attention_required"])
    suggested_action = str(prediction["suggested_action"])

    label_correct = prediction["label"] == row["expected_label"]
    attention_correct = predicted_attention == expected_attention
    false_ignore = expected_attention and not predicted_attention
    unsafe_action = expected_attention and suggested_action in UNSAFE_ACTIONS

    return {
        "email_id": row["email_id"],
        "sender": row["sender"],
        "subject": row["subject"],
        "expected_label": row["expected_label"],
        "predicted_label": prediction["label"],
        "label_correct": str(label_correct).lower(),
        "expected_attention_required": str(expected_attention).lower(),
        "predicted_attention_required": str(predicted_attention).lower(),
        "attention_correct": str(attention_correct).lower(),
        "suggested_action": suggested_action,
        "false_ignore": str(false_ignore).lower(),
        "unsafe_action": str(unsafe_action).lower(),
        "notes": row["notes"],
    }


def classify_email(row: dict[str, str]) -> dict[str, object]:
    """
    Stub classifier for eval v1.

    Replace the body of this function when you are ready to connect the real
    classifier. Keep the returned keys the same:

    - label: str
    - attention_required: bool
    - suggested_action: str
    """

    text = " ".join(
        [
            row.get("sender", ""),
            row.get("subject", ""),
            row.get("body_snippet", ""),
        ]
    ).lower()

    if "invoice" in text or "billing" in text or "security" in text:
        return {
            "label": "EA/Account",
            "attention_required": True,
            "suggested_action": "review",
        }
    if "job" in text or "recruiter" in text or "product sync" in text:
        return {
            "label": "EA/Work",
            "attention_required": True,
            "suggested_action": "review",
        }
    if "confirm" in text or "moved to 3 pm" in text:
        return {
            "label": "EA/Personal",
            "attention_required": True,
            "suggested_action": "review",
        }
    if "receipt" in text or "trip" in text:
        return {
            "label": "EA/Travel",
            "attention_required": False,
            "suggested_action": "keep",
        }
    if "shipped" in text or "order" in text:
        return {
            "label": "EA/Shopping",
            "attention_required": False,
            "suggested_action": "keep",
        }
    if "sale" in text or "promo" in text:
        return {
            "label": "EA/Promotions",
            "attention_required": False,
            "suggested_action": "archive",
        }
    return {
        "label": "EA/Newsletter",
        "attention_required": False,
        "suggested_action": "ignore",
    }


def compute_metrics(results: list[dict[str, str]]) -> dict[str, float | int]:
    total = len(results)
    label_correct_count = sum(row["label_correct"] == "true" for row in results)

    attention_rows = [row for row in results if row["expected_attention_required"] == "true"]
    attention_true_positives = sum(
        row["expected_attention_required"] == "true"
        and row["predicted_attention_required"] == "true"
        for row in results
    )

    false_ignore_count = sum(row["false_ignore"] == "true" for row in results)
    unsafe_action_count = sum(row["unsafe_action"] == "true" for row in results)

    attention_required_recall = (
        attention_true_positives / len(attention_rows) if attention_rows else 0.0
    )

    return {
        "label_accuracy": label_correct_count / total if total else 0.0,
        "attention_required_recall": attention_required_recall,
        "false_ignore_count": false_ignore_count,
        "unsafe_action_count": unsafe_action_count,
    }


def write_results(
    path: Path,
    results: list[dict[str, str]],
    metrics: dict[str, float | int],
) -> None:
    fieldnames = [
        "email_id",
        "sender",
        "subject",
        "expected_label",
        "predicted_label",
        "label_correct",
        "expected_attention_required",
        "predicted_attention_required",
        "attention_correct",
        "suggested_action",
        "false_ignore",
        "unsafe_action",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
        writer.writerow({})
        writer.writerow(
            {
                "email_id": "SUMMARY",
                "expected_label": f"label_accuracy={metrics['label_accuracy']:.4f}",
                "predicted_label": f"attention_required_recall={metrics['attention_required_recall']:.4f}",
                "label_correct": f"false_ignore_count={metrics['false_ignore_count']}",
                "expected_attention_required": f"unsafe_action_count={metrics['unsafe_action_count']}",
            }
        )


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() == "true"


if __name__ == "__main__":
    raise SystemExit(main())
