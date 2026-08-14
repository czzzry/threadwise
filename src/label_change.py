from __future__ import annotations

from dataclasses import dataclass

from src.label_taxonomy import CANONICAL_LABEL_ORDER


VALID_LABEL_CHANGE_OPERATIONS = {"only", "add", "remove", "replace"}
MAX_SELECTED_LABELS = 3
LEGACY_SINGLE_LABEL_COMPATIBILITY = "legacy-single-label"


class LabelChangeError(ValueError):
    """A label-set request is unsafe or cannot be applied exactly."""


@dataclass(frozen=True)
class NormalizedLabelChange:
    operation: str
    labels_before: tuple[str, ...]
    target_labels: tuple[str, ...]
    source_labels: tuple[str, ...]
    labels_after: tuple[str, ...]
    primary_label: str
    interpretation: dict
    schema_version: int = 1

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "labels_before": list(self.labels_before),
            "target_labels": list(self.target_labels),
            "source_labels": list(self.source_labels),
            "labels_after": list(self.labels_after),
            "primary_label": self.primary_label,
            "interpretation": dict(self.interpretation),
        }


def normalize_label_change(payload: dict, *, allow_noop: bool = False) -> NormalizedLabelChange:
    if not isinstance(payload, dict):
        raise LabelChangeError("The approved label change is missing or malformed.")
    if int(payload.get("schema_version") or 1) != 1:
        raise LabelChangeError("This label-change preview is no longer supported. Preview it again.")
    operation = str(payload.get("operation") or "").strip().lower()
    if operation not in VALID_LABEL_CHANGE_OPERATIONS:
        raise LabelChangeError("Choose one label operation: only, add, remove, or replace.")
    before = _canonical_labels(payload.get("labels_before"), "labels_before")
    targets = _canonical_labels(payload.get("target_labels"), "target_labels")
    sources = _canonical_labels(payload.get("source_labels"), "source_labels")
    if operation in {"only", "add", "replace"} and not targets:
        raise LabelChangeError(f"{operation.title()} needs at least one target label.")
    if operation == "remove" and not sources:
        # `target_labels` is accepted as a compatibility spelling for removal.
        sources, targets = targets, ()
    if operation in {"remove", "replace"} and not sources:
        raise LabelChangeError(f"{operation.title()} needs at least one source label.")
    if operation != "replace" and sources and operation != "remove":
        raise LabelChangeError(f"{operation.title()} cannot include source labels.")
    if set(sources) & set(targets):
        raise LabelChangeError("A label cannot be both removed and added in the same change.")
    missing_sources = [label for label in sources if label not in before]
    if missing_sources:
        raise LabelChangeError("The labels to remove are no longer on this email. Preview it again.")

    if operation == "only":
        after = list(targets)
    elif operation == "add":
        after = [*before, *(label for label in targets if label not in before)]
    elif operation == "remove":
        after = [label for label in before if label not in sources]
    else:
        first_removed = min(before.index(label) for label in sources)
        remaining = [label for label in before if label not in sources and label not in targets]
        after = remaining[:first_removed] + list(targets) + remaining[first_removed:]

    after = list(dict.fromkeys(after))
    if len(after) > MAX_SELECTED_LABELS:
        raise LabelChangeError("Threadwise supports at most three labels on one email.")
    if not after:
        raise LabelChangeError("A selected email must keep at least one Threadwise label.")
    if tuple(after) == before and not allow_noop:
        raise LabelChangeError("This request would not change the selected email.")
    interpretation = _normalize_interpretation(payload.get("interpretation") or {})
    return NormalizedLabelChange(
        operation=operation,
        labels_before=before,
        target_labels=targets,
        source_labels=sources,
        labels_after=tuple(after),
        primary_label=after[0],
        interpretation=interpretation,
    )


def require_current_baseline(change: NormalizedLabelChange, current_labels: list[str]) -> None:
    current = _canonical_labels(current_labels, "current labels")
    if current != change.labels_before:
        raise LabelChangeError("This email's labels changed after the preview. Preview the correction again.")


def legacy_only_change(*, labels_before: list[str], target_label: str, interpretation: dict) -> dict:
    normalized = normalize_label_change(
        {
            "schema_version": 1,
            "operation": "only",
            "labels_before": labels_before,
            "target_labels": [target_label],
            "source_labels": [],
            "interpretation": interpretation,
        },
        allow_noop=True,
    ).to_dict()
    return {
        **normalized,
        "compatibility": LEGACY_SINGLE_LABEL_COMPATIBILITY,
    }


def is_legacy_single_label_change(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    return bool(
        payload.get("compatibility") == LEGACY_SINGLE_LABEL_COMPATIBILITY
        and str(payload.get("operation") or "").strip().lower() == "only"
        and isinstance(payload.get("target_labels"), list)
        and len(payload["target_labels"]) == 1
        and isinstance(payload.get("labels_after"), list)
        and len(payload["labels_after"]) == 1
    )


def _canonical_labels(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise LabelChangeError(f"{field} must be a list of canonical labels.")
    labels: list[str] = []
    for raw in value:
        label = str(raw or "").strip()
        if label not in CANONICAL_LABEL_ORDER:
            raise LabelChangeError(f"Unknown Threadwise label: {label or '(blank)'}." )
        if label in labels:
            raise LabelChangeError(f"Duplicate Threadwise label: {label}.")
        labels.append(label)
    return tuple(labels)


def _normalize_interpretation(value: dict) -> dict:
    source = str(value.get("source") or "manual").strip().lower()
    if source not in {"llm", "manual", "deterministic", "fallback"}:
        raise LabelChangeError("Unknown interpretation source.")
    status = str(value.get("status") or ("reviewed" if source in {"llm", "manual"} else "fallback")).strip().lower()
    if status not in {"reviewed", "fallback"}:
        raise LabelChangeError("Unknown interpretation status.")
    return {
        "source": source,
        "status": status,
        "model": str(value.get("model") or "").strip(),
        "rationale": str(value.get("rationale") or "").strip(),
    }
