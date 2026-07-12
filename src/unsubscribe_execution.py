import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from src.local_artifacts import (
    load_json_or_default,
    unsubscribe_execution_audit_path,
    unsubscribe_selections_path,
    write_json,
)


class UnsubscribeExecutor:
    def __init__(self, storage_dir: Path, transport=None) -> None:
        self._storage_dir = storage_dir
        self._transport = transport or _default_transport

    def preview_selected_candidates(self) -> dict:
        selected_candidates = self._selected_candidates()
        preview_items = [self._build_preview_item(candidate) for candidate in selected_candidates]
        ready_count = sum(1 for item in preview_items if item["status"] == "ready")
        unsupported_count = sum(1 for item in preview_items if item["status"] == "unsupported")
        return {
            "selected_count": len(preview_items),
            "ready_count": ready_count,
            "unsupported_count": unsupported_count,
            "candidates": preview_items,
        }

    def execute_selected_candidates(self) -> dict:
        preview = self.preview_selected_candidates()
        audit = self._load_audit()
        audit_candidates = audit.setdefault("candidates", {})
        executed_count = 0
        failed_count = 0
        unsupported_count = 0

        for item in preview["candidates"]:
            candidate_record = audit_candidates.setdefault(
                item["list_key"],
                {
                    "provider": item["provider"],
                    "account_id": item["account_id"],
                    "display_name": item["display_name"],
                    "sender": item["sender"],
                    "attempts": [],
                },
            )
            attempt = {
                "attempted_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
                "status": item["status"],
                "method": item["method"],
                "url": item.get("url"),
                "notes": item["notes"],
            }

            if item["status"] == "ready":
                try:
                    self._transport(item["http_method"], item["url"], item.get("request_body"))
                    attempt["status"] = "executed"
                    executed_count += 1
                except Exception as exc:
                    attempt["status"] = "failed"
                    attempt["notes"] = str(exc)
                    failed_count += 1
            else:
                unsupported_count += 1

            candidate_record["attempts"].append(attempt)

        write_json(self._audit_path(), audit)
        return {
            "selected_count": preview["selected_count"],
            "executed_count": executed_count,
            "failed_count": failed_count,
            "unsupported_count": unsupported_count,
            "candidates": preview["candidates"],
        }

    def latest_attempt_map(self) -> dict[str, dict]:
        audit = self._load_audit()
        latest: dict[str, dict] = {}
        for list_key, candidate in audit.get("candidates", {}).items():
            attempts = candidate.get("attempts") or []
            if attempts:
                latest[list_key] = attempts[-1]
        return latest

    def _selected_candidates(self) -> list[dict]:
        selections = self._load_selections()
        return [
            candidate
            for candidate in selections.get("candidates", {}).values()
            if candidate.get("decision_state") == "selected"
        ]

    def _build_preview_item(self, candidate: dict) -> dict:
        list_unsubscribe = candidate.get("list_unsubscribe") or ""
        list_unsubscribe_post = candidate.get("list_unsubscribe_post") or ""
        http_url = _first_http_url(list_unsubscribe)
        mailto_url = _first_mailto_url(list_unsubscribe)

        item = {
            "provider": candidate.get("provider"),
            "account_id": candidate.get("account_id"),
            "list_key": candidate.get("list_key"),
            "display_name": candidate.get("display_name"),
            "sender": candidate.get("sender"),
            "status": "unsupported",
            "method": "unsupported",
            "http_method": None,
            "url": http_url or mailto_url,
            "request_body": None,
            "notes": "No supported unsubscribe method found.",
        }

        if http_url and list_unsubscribe_post.strip().lower() == "list-unsubscribe=one-click":
            item["status"] = "ready"
            item["method"] = "one-click-post"
            item["http_method"] = "POST"
            item["request_body"] = "List-Unsubscribe=One-Click"
            item["notes"] = "Ready for one-click HTTPS unsubscribe."
            return item

        if mailto_url and not http_url:
            item["notes"] = "Unsupported: mailto unsubscribe requires manual follow-up."
            return item

        if http_url:
            if _is_provider_error_prone_url(http_url):
                item["notes"] = (
                    "Unsupported: provider-hosted unsubscribe link may open a signed-in error page. "
                    "Review manually instead of treating the raw link as a Threadwise action."
                )
            else:
                item["notes"] = "Unsupported: HTTP unsubscribe link is missing one-click confirmation metadata."
            return item

        return item

    def _load_selections(self) -> dict:
        return load_json_or_default(unsubscribe_selections_path(self._storage_dir), {"candidates": {}})

    def _load_audit(self) -> dict:
        return load_json_or_default(self._audit_path(), {"candidates": {}})

    def _audit_path(self) -> Path:
        return unsubscribe_execution_audit_path(self._storage_dir)


def _first_http_url(value: str) -> str | None:
    for token in _split_list_unsubscribe(value):
        normalized = token.strip().strip("<>").strip()
        if normalized.startswith("https://") or normalized.startswith("http://"):
            return normalized
    return None


def _first_mailto_url(value: str) -> str | None:
    for token in _split_list_unsubscribe(value):
        normalized = token.strip().strip("<>").strip()
        if normalized.startswith("mailto:"):
            return normalized
    return None


def _split_list_unsubscribe(value: str) -> list[str]:
    return [token for token in value.split(",") if token.strip()]


def _is_provider_error_prone_url(value: str) -> bool:
    hostname = (urlparse(value).hostname or "").lower()
    return hostname == "linkedin.com" or hostname.endswith(".linkedin.com")


def _default_transport(method: str, url: str, body: str | None = None) -> dict:
    data = body.encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {"status_code": response.getcode()}
    except urllib.error.HTTPError as exc:
        return {"status_code": exc.code}
