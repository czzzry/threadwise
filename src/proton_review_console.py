from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from src.gmail_companion_rendering import escape_html
from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.local_artifacts import load_json_or_default, write_json


class ProtonReviewConsole:
    """A bounded, label-only review queue backed by Proton Mail Bridge."""

    def __init__(
        self,
        proton_client: object,
        classification_ledger_path: Path,
        review_state_path: Path,
        *,
        max_results: int = 10_000,
    ) -> None:
        self._proton = proton_client
        self._classification_ledger_path = classification_ledger_path
        self._review_state_path = review_state_path
        self._max_results = max_results
        self._lock = threading.Lock()

    def state(self) -> dict:
        with self._lock:
            return self._state_unlocked()

    def acknowledge(self, message_id: str) -> dict:
        with self._lock:
            self._require_pending_unlocked(message_id)
            self._record_decision_unlocked(
                message_id,
                decision="looks-right",
                provider_verified=False,
            )
            return self._state_unlocked()

    def apply_label(self, message_id: str, internal_label: str) -> dict:
        if internal_label not in CANONICAL_LABEL_ORDER:
            raise ValueError("Choose one of Threadwise's allowed labels.")
        with self._lock:
            current = self._require_pending_unlocked(message_id)
            label_name = gmail_label_name(internal_label)
            write_result = self._proton.apply_label(message_id, label_name)
            if not write_result.get("inbox_preserved") or write_result.get("destructive_actions"):
                raise RuntimeError("Proton label write violated the label-only safety contract.")

            rfc_message_id = str(current.get("rfc_message_id") or "").strip()
            if not rfc_message_id:
                raise RuntimeError("Could not verify the Proton label because the email has no Message-ID header.")
            if not self._proton.message_has_label(rfc_message_id, label_name):
                raise RuntimeError("Proton did not confirm the label after the write; the review item was not advanced.")

            self._record_decision_unlocked(
                message_id,
                decision="label-added",
                provider_verified=True,
                internal_label=internal_label,
                label=label_name,
                provider_mailbox=str(write_result.get("mailbox") or ""),
            )
            return self._state_unlocked()

    def _state_unlocked(self) -> dict:
        classification = load_json_or_default(
            self._classification_ledger_path,
            {"provider": "protonmail", "messages": {}},
        )
        review_state = load_json_or_default(
            self._review_state_path,
            {"provider": "protonmail", "messages": {}},
        )
        live_ids = set(self._proton.list_messages(self._max_results))
        reviewed = review_state.get("messages") or {}
        candidates: list[tuple[float, str, dict]] = []
        for message_id, record in (classification.get("messages") or {}).items():
            if message_id not in live_ids or message_id in reviewed:
                continue
            double_check = record.get("double_check")
            if not isinstance(double_check, dict):
                continue
            confidence = float(double_check.get("confidence", 1.0))
            candidates.append((confidence, message_id, record))
        candidates.sort(key=lambda item: (item[0], item[1]))

        current = None
        if candidates:
            confidence, message_id, record = candidates[0]
            message = self._proton.get_message(message_id)
            current = {
                "message_id": message_id,
                "sender": str(message.get("sender") or ""),
                "subject": str(message.get("subject") or ""),
                "date": str(message.get("date") or ""),
                "body": str(message.get("body") or ""),
                "rfc_message_id": str(message.get("rfc_message_id") or ""),
                "suggested_internal_label": str(record.get("internal_label") or ""),
                "suggested_label": str(record.get("label") or ""),
                "reason": str(record.get("reason") or ""),
                "confidence": confidence,
            }
        return {
            "provider": "protonmail",
            "queue_name": "Double check",
            "remaining_count": len(candidates),
            "reviewed_count": len(reviewed),
            "current": current,
            "allowed_labels": [
                {"internal_label": label, "display_label": gmail_label_name(label)}
                for label in CANONICAL_LABEL_ORDER
            ],
            "safety": {
                "label_only": True,
                "inbox_preserved": True,
                "destructive_actions": [],
            },
        }

    def _require_pending_unlocked(self, message_id: str) -> dict:
        state = self._state_unlocked()
        current = state.get("current")
        if not current or current.get("message_id") != message_id:
            raise ValueError("That Proton review item is no longer current. Refresh the queue and try again.")
        return current

    def _record_decision_unlocked(
        self,
        message_id: str,
        *,
        decision: str,
        provider_verified: bool,
        **details: object,
    ) -> None:
        state = load_json_or_default(
            self._review_state_path,
            {"provider": "protonmail", "messages": {}},
        )
        decided_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        state.setdefault("messages", {})[message_id] = {
            "decision": decision,
            "decided_at": decided_at,
            "provider_verified": provider_verified,
            "inbox_preserved": True,
            "destructive_actions": [],
            **details,
        }
        state["updated_at"] = decided_at
        write_json(self._review_state_path, state)


def render_proton_review_page(state: dict) -> str:
    current = state.get("current")
    remaining = int(state.get("remaining_count") or 0)
    reviewed = int(state.get("reviewed_count") or 0)
    options = "".join(
        f'<option value="{escape_html(item["internal_label"])}"'
        f'{" selected" if current and item["internal_label"] == current.get("suggested_internal_label") else ""}>'
        f'{escape_html(item["display_label"])}</option>'
        for item in state.get("allowed_labels") or []
    )
    if current:
        card = f"""
        <article class="message-card" data-proton-current-message="{escape_html(current['message_id'])}">
          <div class="eyebrow">Proton · needs your review</div>
          <h2>{escape_html(current.get('subject') or '(No subject)')}</h2>
          <div class="sender">{escape_html(current.get('sender') or 'Unknown sender')}</div>
          <div class="date">{escape_html(current.get('date') or '')}</div>
          <section class="suggestion">
            <strong>Threadwise suggests {escape_html(current.get('suggested_label') or 'a label')}</strong>
            <div>{escape_html(current.get('reason') or 'No reason was stored.')}</div>
          </section>
          <details class="body" open>
            <summary>Full email context</summary>
            <pre>{escape_html(current.get('body') or 'No readable body was available.')}</pre>
          </details>
          <div id="action-status" class="status" role="status" aria-live="polite"></div>
          <button id="looks-right" class="action primary" type="button">Looks right · Next</button>
          <div class="correction">
            <label for="target-label">Add another label to this email</label>
            <select id="target-label">{options}</select>
            <button id="apply-label" class="action secondary" type="button">Add label · Next</button>
          </div>
        </article>
        """
    else:
        card = """
        <article class="message-card caught-up" data-proton-caught-up>
          <div class="eyebrow">Proton · review complete</div>
          <h2>Nothing else needs a double check</h2>
          <p>Threadwise will not re-offer the messages you reviewed in this console.</p>
        </article>
        """

    safe_state = json.dumps({"message_id": current.get("message_id") if current else None}).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Threadwise Proton Review</title>
  <style>
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-height:100vh; padding:clamp(12px,4vw,34px); color:#241812; font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:radial-gradient(circle at 18px 18px,rgba(36,24,18,.05) 2px,transparent 2px) 0 0/36px 36px,linear-gradient(135deg,#f7efe0,#fdfaf2 52%,#e7f3ee); }}
    main {{ width:min(880px,100%); margin:0 auto; border:2px solid #241812; border-radius:20px; overflow:hidden; background:#fff7e8; box-shadow:0 16px 40px rgba(36,24,18,.14); }}
    header,.message-card,.safety {{ padding:clamp(16px,3vw,26px); }}
    header {{ display:flex; align-items:center; justify-content:space-between; gap:16px; border-bottom:1px solid rgba(36,24,18,.28); }}
    .brand {{ display:flex; align-items:center; gap:12px; }}
    .brand img {{ width:44px; height:44px; border:1px solid rgba(36,24,18,.34); border-radius:12px; }}
    .eyebrow {{ color:#6b6255; font-size:.72rem; font-weight:850; letter-spacing:.13em; text-transform:uppercase; }}
    h1,h2 {{ margin:5px 0 8px; line-height:1.12; }}
    h1 {{ font-size:1.45rem; }} h2 {{ font-size:1.55rem; }}
    .count {{ white-space:nowrap; border:1px solid rgba(36,24,18,.28); border-radius:999px; padding:7px 11px; background:#f1eadf; font-weight:800; }}
    .message-card {{ background:#fffdf7; }}
    .sender,.date {{ color:#6b6255; overflow-wrap:anywhere; }} .date {{ margin-top:3px; font-size:.86rem; }}
    .suggestion,.body,.correction,.safety {{ margin-top:16px; border:1px solid rgba(36,24,18,.25); border-radius:13px; background:#f5efe2; padding:14px; line-height:1.45; }}
    .suggestion strong {{ display:block; margin-bottom:5px; }}
    .body summary {{ cursor:pointer; font-weight:850; }}
    pre {{ margin:14px 0 0; white-space:pre-wrap; overflow-wrap:anywhere; font:inherit; line-height:1.5; }}
    .correction {{ display:grid; gap:10px; background:#fff7e8; }}
    label {{ font-weight:800; }} select {{ width:100%; padding:10px 12px; border:2px solid #241812; border-radius:10px; background:#fffdf7; color:#241812; font:inherit; }}
    .action {{ width:100%; margin-top:14px; border:2px solid #241812; border-radius:11px; padding:11px 14px; color:#241812; font:inherit; font-weight:850; cursor:pointer; box-shadow:3px 3px 0 #241812; }}
    .primary {{ background:#2eb67d; }} .secondary {{ margin-top:0; background:#ebe4d7; }}
    .action:disabled {{ cursor:wait; opacity:.65; }}
    .status {{ min-height:22px; margin-top:12px; color:#0f6259; font-weight:750; }}
    .status.error {{ color:#9b2c2c; }}
    .safety {{ margin:0; border-width:1px 0 0; border-radius:0; color:#5d5342; background:#eef6f2; }}
    a {{ color:#5d5342; font-weight:800; }}
    :where(button,a,select,summary):focus-visible {{ outline:3px solid #3d6df2; outline-offset:2px; }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="brand"><img src="/assets/brand/threadwise-app-icon.png" alt=""><div><div class="eyebrow">Threadwise companion</div><h1>Proton review</h1><a href="/daily-dashboard">Back to daily dashboard</a></div></div>
      <div class="count"><span data-remaining-count>{remaining}</span> remaining · {reviewed} reviewed</div>
    </header>
    {card}
    <aside class="safety"><strong>Label-only trial.</strong> No email will be archived, deleted, moved, or sent. “Looks right” changes only Threadwise's local review record.</aside>
  </main>
  <script>
    const current = {safe_state};
    const statusNode = document.getElementById('action-status');
    const buttons = Array.from(document.querySelectorAll('button'));
    async function submit(path, payload, workingCopy) {{
      buttons.forEach((button) => button.disabled = true);
      if (statusNode) {{ statusNode.className = 'status'; statusNode.textContent = workingCopy; }}
      try {{
        const response = await fetch(path, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(payload)}});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Threadwise could not complete this action.');
        if (statusNode) statusNode.textContent = 'Done. Loading the next Proton email…';
        window.location.reload();
      }} catch (error) {{
        buttons.forEach((button) => button.disabled = false);
        if (statusNode) {{ statusNode.className = 'status error'; statusNode.textContent = error.message; }}
      }}
    }}
    document.getElementById('looks-right')?.addEventListener('click', () => submit('/api/proton-review/acknowledge', {{message_id:current.message_id}}, 'Recording this review…'));
    document.getElementById('apply-label')?.addEventListener('click', () => submit('/api/proton-review/apply-label', {{message_id:current.message_id, internal_label:document.getElementById('target-label').value}}, 'Applying and verifying the Proton label…'));
  </script>
</body>
</html>"""
