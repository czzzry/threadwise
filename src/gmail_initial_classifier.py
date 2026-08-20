"""Optional model assistance for complete initial email classification."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from src.fixture_classifier import FixtureBatchClassifier
from src.label_taxonomy import CANONICAL_LABEL_ORDER
from src.runtime_cascade import OpenAIRuntimeCascadeClient


class ModelAssistedClassifier:
    """Escalate deterministic misses to a model with reviewable best guesses.

    Deterministic matches keep the existing auto-apply behavior. Model output is
    stored as the tentative label set and remains pending for review after the
    provider label write.
    """

    def __init__(
        self,
        model_client: object,
        *,
        deterministic_classifier: FixtureBatchClassifier | None = None,
    ) -> None:
        self._model_client = model_client
        self._deterministic_classifier = deterministic_classifier or FixtureBatchClassifier(
            fixtures_dir=Path(".")
        )

    def classify_messages(self, batch_id: str, messages: list[dict]) -> dict:
        result = self._deterministic_classifier.classify_messages(batch_id, messages)
        messages_by_id = {str(message.get("message_id") or ""): message for message in messages}
        for item in result.get("items") or []:
            if item.get("applied_labels"):
                item["decision_provenance"] = _rules_provenance()
                continue
            self._apply_model_result(
                item,
                messages_by_id.get(str(item.get("message_id") or ""), {}),
            )
        return result

    def _apply_model_result(self, item: dict, message: dict) -> None:
        model_name = str(getattr(self._model_client, "model", "") or "")
        try:
            response = self._model_client.analyze_message(_model_payload(message))
            labels = _valid_labels(response.get("labels") or [])
            abstained = bool(response.get("unresolved") or not labels)
            rationale = str(response.get("rationale") or "").strip()
            confidence = _confidence(response.get("confidence"))
            item["applied_labels"] = labels
            item["near_misses"] = []
            item["confidence_band"] = confidence
            if rationale:
                item["interpretation"] = rationale
            item["decision_provenance"] = {
                "decision_source": "model",
                "llm_used": True,
                "llm_model": model_name,
                "llm_confidence": confidence,
                "llm_abstained": abstained,
                "llm_failed": False,
            }
        except Exception:
            item["near_misses"] = []
            item["decision_provenance"] = {
                "decision_source": "model-failure",
                "llm_used": True,
                "llm_model": model_name,
                "llm_confidence": "",
                "llm_abstained": False,
                "llm_failed": True,
            }
        # A model result remains reviewable even after its tentative label is
        # written. A true model failure has no pretend fallback label.
        item["review_state"] = "pending"
        item.pop("final_labels", None)
        item.pop("review_action", None)


# Compatibility for callers created before the always-label decision.
ReviewOnlyModelAssistedClassifier = ModelAssistedClassifier


def configure_initial_classifier(
    model: str | None,
    *,
    env: Mapping[str, str] | None = None,
    client_factory=None,
    deterministic_classifier: FixtureBatchClassifier | None = None,
) -> tuple[ModelAssistedClassifier | None, dict]:
    """Return the optional classifier and a safe user-visible config status."""
    model_name = str(model or "").strip()
    if not model_name:
        return None, {"state": "disabled", "model": ""}

    environment = os.environ if env is None else env
    api_key = environment.get("EMAIL_AGENT_OPENAI_API_KEY") or environment.get("OPENAI_API_KEY")
    if not api_key:
        return None, {
            "state": "not-ready",
            "model": model_name,
            "reason": "missing-api-key",
        }

    factory = client_factory or (
        lambda selected_model: OpenAIRuntimeCascadeClient(api_key=api_key, model=selected_model)
    )
    try:
        client = factory(model_name)
    except Exception:
        return None, {
            "state": "not-ready",
            "model": model_name,
            "reason": "client-configuration-failed",
        }
    return ModelAssistedClassifier(
        client,
        deterministic_classifier=deterministic_classifier,
    ), {
        "state": "ready",
        "model": model_name,
    }


def _model_payload(message: dict) -> dict:
    return {
        "message_id": str(message.get("message_id") or ""),
        "sender": str(message.get("sender") or ""),
        "subject": str(message.get("subject") or ""),
        "date": str(message.get("date") or ""),
        "snippet": str(message.get("snippet") or ""),
        "body": str(message.get("body") or ""),
        "gmail_label_ids": list(message.get("gmail_label_ids") or []),
    }


def _valid_labels(labels: list) -> list[str]:
    result: list[str] = []
    for label in labels:
        value = str(label)
        if value in CANONICAL_LABEL_ORDER and value not in result:
            result.append(value)
        if len(result) == 3:
            break
    return result


def _confidence(value: object) -> str:
    normalized = str(value or "").lower()
    return normalized if normalized in {"low", "medium", "high"} else "low"


def _rules_provenance() -> dict:
    return {
        "decision_source": "rules",
        "llm_used": False,
        "llm_model": "",
        "llm_confidence": "",
        "llm_abstained": False,
        "llm_failed": False,
    }
