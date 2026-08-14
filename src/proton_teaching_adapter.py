from __future__ import annotations

from collections.abc import Callable

from src.companion_teaching_workflow import TeachingWriteRequest


class ProtonTeachingAdapter:
    """Own verified Proton label writes behind the shared teaching interface."""

    def __init__(self, console_loader: Callable[[], object]) -> None:
        self._console_loader = console_loader

    def apply(self, request: TeachingWriteRequest) -> dict:
        if request.mode == "save-future-rule":
            return _write_summary("no-gmail-write-future-rule-only")

        self.preflight(request)
        label_change = request.label_change or {}
        target_labels = list(label_change.get("target_labels") or []) if label_change else []
        target_label = str((request.semantic_rule or {}).get("target_label") or "")
        if not target_labels and target_label:
            target_labels = [target_label]
        message_ids = [request.current_message_id]
        if request.mode == "apply-included":
            message_ids.extend(sorted(request.included_message_ids))
        elif request.mode == "matching-existing":
            message_ids.extend(
                str(item.get("message_id") or "")
                for item in request.preview_matches
            )
        message_ids = list(dict.fromkeys(message_id for message_id in message_ids if message_id))

        summary = _write_summary("applied")
        console = self._console_loader()
        for message_id in message_ids:
            message_failed = False
            for requested_label in target_labels:
                try:
                    console.apply_companion_label(message_id, requested_label)
                    summary.setdefault("confirmed_labels", {}).setdefault(message_id, []).append(requested_label)
                except Exception as exc:
                    message_failed = True
                    summary.setdefault("errors", []).append({
                        "message_id": message_id,
                        "label": requested_label,
                        "error": str(exc),
                    })
            if message_failed:
                summary["label_write_failed"] += 1
            else:
                summary["messages_written"] += 1
        return summary

    def preflight(self, request: TeachingWriteRequest) -> None:
        label_change = request.label_change or {}
        if label_change and str(label_change.get("operation") or "") != "add":
            raise ValueError(
                "Proton Mail currently supports verified additive label corrections only. Nothing was changed."
            )

    def preview_backfill(self, preview: dict) -> dict:
        console = self._console_loader()
        live_ids = console.live_message_ids()
        local_items = [
            item
            for item in (preview.get("impact") or {}).get("matching_existing_items") or []
            if str(item.get("message_id") or "") in live_ids
        ]
        return {
            "available": True,
            "estimated_count": len(local_items),
            "is_capped": False,
            "requires_confirmation": False,
            "query": "",
            "matches": local_items,
        }


def _write_summary(mode: str) -> dict:
    return {
        "provider": "protonmail",
        "messages_written": 0,
        "inbox_removed": 0,
        "label_write_failed": 0,
        "label_write_skipped": 0,
        "inbox_remove_failed": 0,
        "inbox_remove_skipped": 0,
        "inbox_remove_ineligible": 0,
        "mode": mode,
    }
