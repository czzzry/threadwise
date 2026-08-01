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

        target_label = str((request.semantic_rule or {}).get("target_label") or "")
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
            try:
                console.apply_companion_label(message_id, target_label)
                summary["messages_written"] += 1
            except Exception as exc:
                summary["label_write_failed"] += 1
                summary.setdefault("errors", []).append({
                    "message_id": message_id,
                    "error": str(exc),
                })
        return summary

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
