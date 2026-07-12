import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import urllib.error
import urllib.request

from src.label_taxonomy import CANONICAL_LABEL_ORDER
from src.local_artifacts import evaluation_report_path, evaluations_dir, load_json, write_json


@dataclass
class ReviewedMessage:
    batch_id: str
    message_id: str
    sender: str
    subject: str
    snippet: str
    body: str
    final_labels: list[str]
    heuristic_labels: list[str]


class ReviewedCorpusLoader:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def load_reviewed_messages(self, limit: int | None = None) -> list[ReviewedMessage]:
        messages: list[ReviewedMessage] = []
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_json(batch_path)
            for item in batch.get("items", []):
                if item.get("review_state") != "reviewed":
                    continue
                messages.append(
                    ReviewedMessage(
                        batch_id=batch["batch_id"],
                        message_id=item["message_id"],
                        sender=item.get("sender", ""),
                        subject=item.get("subject", ""),
                        snippet=item.get("snippet") or "",
                        body=item.get("body") or "",
                        final_labels=list(item.get("final_labels") or []),
                        heuristic_labels=list(item.get("applied_labels") or []),
                    )
                )
                if limit is not None and len(messages) >= limit:
                    return messages
        return messages


class OpenAIShadowLabelClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @classmethod
    def from_env(cls, model: str) -> "OpenAIShadowLabelClient":
        api_key = os.environ.get("EMAIL_AGENT_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "EMAIL_AGENT_OPENAI_API_KEY or OPENAI_API_KEY is required for shadow model evaluation."
            )
        return cls(api_key=api_key, model=model)

    def classify(self, message: ReviewedMessage) -> dict:
        prompt = _shadow_label_prompt(message)
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an executive inbox triage classifier. "
                        "Optimize for a very busy CEO with little time for noise. "
                        "Return strict JSON with keys labels and reason. "
                        "labels must be an array of zero to three labels from the allowed taxonomy only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API request failed: {exc.code} {body}") from exc

        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        labels = [
            label
            for label in parsed.get("labels", [])
            if label in CANONICAL_LABEL_ORDER
        ][:3]
        return {
            "labels": labels,
            "reason": parsed.get("reason", ""),
        }


class ShadowLabelEvaluator:
    def __init__(self, storage_dir: Path, model_client: OpenAIShadowLabelClient | None = None) -> None:
        self._storage_dir = storage_dir
        self._model_client = model_client

    def run(self, limit: int | None = None, disagreement_limit: int = 25) -> dict:
        corpus = ReviewedCorpusLoader(self._storage_dir).load_reviewed_messages(limit=limit)
        evaluated_items = []
        model_available = self._model_client is not None

        for message in corpus:
            model_prediction = {"labels": [], "reason": "Model evaluation not run."}
            if self._model_client is not None:
                model_prediction = self._model_client.classify(message)

            evaluated_items.append(
                {
                    "batch_id": message.batch_id,
                    "message_id": message.message_id,
                    "sender": message.sender,
                    "subject": message.subject,
                    "ground_truth": sorted(message.final_labels),
                    "heuristic_labels": sorted(message.heuristic_labels),
                    "model_labels": sorted(model_prediction["labels"]),
                    "model_reason": model_prediction["reason"],
                }
            )

        report = build_shadow_eval_report(evaluated_items, model_available, disagreement_limit)
        report_path = self._write_report(report)
        report["report_path"] = str(report_path)
        return report

    def _write_report(self, report: dict) -> Path:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        report_path = evaluation_report_path(self._storage_dir, f"shadow-label-eval-{timestamp}")
        write_json(report_path, report)
        return report_path


def build_shadow_eval_report(
    evaluated_items: list[dict],
    model_available: bool,
    disagreement_limit: int = 25,
) -> dict:
    overall = {
        "reviewed_count": len(evaluated_items),
        "heuristic": _prediction_metrics(evaluated_items, "heuristic_labels"),
    }
    if model_available:
        overall["model"] = _prediction_metrics(evaluated_items, "model_labels")

    per_label = {
        "heuristic": _per_label_metrics(evaluated_items, "heuristic_labels"),
    }
    if model_available:
        per_label["model"] = _per_label_metrics(evaluated_items, "model_labels")

    disagreements = {
        "model_better_than_heuristic": [],
        "heuristic_better_than_model": [],
    }
    comparison_candidates = []
    if model_available:
        for item in evaluated_items:
            truth = set(item["ground_truth"])
            heuristic = set(item["heuristic_labels"])
            model = set(item["model_labels"])
            heuristic_exact = heuristic == truth
            model_exact = model == truth
            compact = {
                "batch_id": item["batch_id"],
                "message_id": item["message_id"],
                "sender": item["sender"],
                "subject": item["subject"],
                "ground_truth": item["ground_truth"],
                "heuristic_labels": item["heuristic_labels"],
                "model_labels": item["model_labels"],
                "model_reason": item["model_reason"],
            }
            if model != truth:
                comparison_candidates.append(compact)
            if model_exact and not heuristic_exact:
                disagreements["model_better_than_heuristic"].append(compact)
            elif heuristic_exact and not model_exact:
                disagreements["heuristic_better_than_model"].append(compact)

        disagreements["model_better_than_heuristic"] = disagreements["model_better_than_heuristic"][
            :disagreement_limit
        ]
        disagreements["heuristic_better_than_model"] = disagreements["heuristic_better_than_model"][
            :disagreement_limit
        ]
        comparison_candidates = comparison_candidates[:disagreement_limit]

    report = {
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "taxonomy": list(CANONICAL_LABEL_ORDER),
        "overall": overall,
        "per_label": per_label,
        "disagreements": disagreements,
    }
    if model_available:
        report["comparison_candidates"] = comparison_candidates
    return report


def _prediction_metrics(items: list[dict], key: str) -> dict:
    exact_matches = 0
    overlap_matches = 0
    unlabeled_matches = 0
    for item in items:
        truth = set(item["ground_truth"])
        predicted = set(item[key])
        if predicted == truth:
            exact_matches += 1
        if predicted.intersection(truth):
            overlap_matches += 1
        if not truth and not predicted:
            unlabeled_matches += 1

    reviewed_count = len(items) or 1
    return {
        "exact_match_count": exact_matches,
        "exact_match_rate": round(exact_matches / reviewed_count * 100, 1),
        "overlap_count": overlap_matches,
        "overlap_rate": round(overlap_matches / reviewed_count * 100, 1),
        "unlabeled_match_count": unlabeled_matches,
        "unlabeled_match_rate": round(unlabeled_matches / reviewed_count * 100, 1),
    }


def _per_label_metrics(items: list[dict], key: str) -> dict[str, dict]:
    result = {}
    for label in CANONICAL_LABEL_ORDER:
        tp = fp = fn = 0
        for item in items:
            truth = set(item["ground_truth"])
            predicted = set(item[key])
            if label in truth and label in predicted:
                tp += 1
            elif label not in truth and label in predicted:
                fp += 1
            elif label in truth and label not in predicted:
                fn += 1

        precision = round(tp / (tp + fp) * 100, 1) if (tp + fp) else None
        recall = round(tp / (tp + fn) * 100, 1) if (tp + fn) else None
        result[label] = {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": precision,
            "recall": recall,
        }
    return result


def _shadow_label_prompt(message: ReviewedMessage) -> str:
    allowed = ", ".join(CANONICAL_LABEL_ORDER)
    return (
        "Classify this email for executive inbox triage and retrieval.\n"
        f"Allowed labels: {allowed}\n"
        "Decision order:\n"
        "1. Does this require or strongly merit the user's attention now?\n"
        "2. If not, is it genuinely useful to retrieve later as a record or logistics item?\n"
        "3. If not, label it spam-low-value even if the topic sounds important.\n"
        "Rules:\n"
        "- Use zero to three labels only, but prefer a single label unless a second label is clearly necessary.\n"
        "- Do not invent labels.\n"
        "- Judge by actual usefulness, not apparent importance or topic keywords.\n"
        "- Important-looking words like IMPORTANT, urgent, travel, finance, network, update, or offer do not make a message useful.\n"
        "- Unsolicited promotions, surveys, platform nudges, generic digests, and low-value marketing default to spam-low-value.\n"
        "- If a message is promotional noise, spam-low-value usually overrides topical labels like travel, financial-account, newsletter, or promotions.\n"
        "- Exception: reminders or alerts the user likely requested or intentionally set up, such as wishlist alerts or requested price-drop reminders, should not default to spam-low-value.\n"
        "- Use reply-needed only when a real human response or explicit action from the user is likely expected.\n"
        "- Use account-security for login codes, verification, resets, or finishing an account flow the user initiated.\n"
        "- Use job-related or reply-needed for job application and interview pipeline mail. Actual application or hiring-process mail must never be spam-low-value.\n"
        "- For job mail: interviews, scheduling, recruiter follow-up, and next-step asks should bias strongly to reply-needed. Application receipts or status updates should bias to job-related.\n"
        "- LinkedIn or social network growth nudges, add-a-person prompts, profile alerts, and similar platform engagement prompts default to spam-low-value.\n"
        "- Use travel, shopping-order, receipt-billing, financial-account, or calendar-event only for genuine records, logistics, or retrieval-useful items, not because of topic words alone.\n"
        "- The user cares about account statements and records, not helping institutions with surveys.\n"
        "- Return JSON: {\"labels\": [...], \"reason\": \"...\"}\n\n"
        f"Sender: {message.sender}\n"
        f"Subject: {message.subject}\n"
        f"Snippet: {message.snippet}\n"
        f"Body: {message.body}\n"
    )
