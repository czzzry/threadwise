

from urllib.parse import quote


def dashboard_item_identity(item: dict) -> str:
    message_id = str(item.get("message_id") or "").strip()
    if message_id:
        return f"message:{message_id}"
    thread_id = str(item.get("thread_id") or "").strip()
    if thread_id:
        return f"thread:{thread_id}"
    sender = " ".join(str(item.get("sender") or "").split()).casefold()
    subject = " ".join(str(item.get("subject") or "").split()).casefold()
    if sender or subject:
        return f"sender-subject:{sender}|{subject}"
    return ""


def unsubscribe_section_key(detail: dict, preview: dict) -> str:
    if detail.get("decision_state") == "selected":
        return "queued"
    if preview.get("status") == "ready":
        return "ready"
    return "manual"


def render_unsubscribe_section(key: str, title: str, description: str, rows: list[str]) -> str:
    return (
        f'<section class="unsubscribe-group" data-unsubscribe-group="{escape_html(key)}">'
        f'<div class="eyebrow">{escape_html(title)}</div>'
        f'<h2>{escape_html(title)}</h2>'
        f'<p>{escape_html(description)}</p>'
        f'<div class="unsubscribe-list">{"".join(rows)}</div>'
        '</section>'
    )


def render_unsubscribe_row(
    detail: dict,
    preview: dict,
    *,
    action_html: str = "",
    focused: bool = False,
) -> str:
    latest_execution = detail.get("latest_execution") or {}
    decision_state = detail.get("decision_state") or "undecided"
    checked = " checked" if decision_state == "selected" else ""
    focus_html = '<div class="focus-note">Opened from inbox</div>' if focused else ""
    latest_status = latest_execution.get("status") or "none"
    latest_notes = latest_execution.get("notes") or "No recorded execution yet."
    return (
        f'<article class="unsubscribe-row{" focused" if focused else ""}" data-unsubscribe-row '
        f'data-unsubscribe-candidate="{escape_html(detail.get("list_key") or "")}">'
        '<div class="selection-cell">'
        f'<input type="checkbox" data-unsubscribe-selection value="{escape_html(detail.get("list_key") or "")}"{checked} '
        f'aria-label="Queue {escape_html(detail.get("display_name") or "subscription")}">'
        '</div>'
        f'<div class="identity-cell">{focus_html}<h3>{escape_html(detail.get("display_name") or "(unknown list)")}</h3>'
        f'<div class="address">{escape_html(detail.get("sender") or "(unknown sender)")}</div></div>'
        f'<div class="evidence-cell"><strong>{detail.get("evidence_count", 0)}</strong><span>messages</span></div>'
        '<div class="readiness-cell">'
        f'<strong>{escape_html(preview.get("notes") or "Manual follow-up")}</strong>'
        f'<span>{escape_html(preview.get("method") or "unsupported")}</span></div>'
        '<div class="attempt-cell"><strong>Latest attempt</strong>'
        f'<span>{escape_html(latest_status)} · {escape_html(latest_notes)}</span></div>'
        f'<div class="row-action-cell">{action_html}</div>'
        '</article>'
    )

def render_dashboard_section(title: str, description: str, cards_html: str) -> str:
    return (
        '<section class="card">'
        f'<div class="eyebrow">{escape_html(title)}</div>'
        f'<h2>{escape_html(title)}</h2>'
        f'<p>{escape_html(description)}</p>'
        f'<div class="stack">{cards_html}</div>'
        '</section>'
    )

def render_dashboard_email_cards(items: list[dict], empty_label: str, *, allow_attention_feedback: bool = False) -> str:
    if not items:
        return f'<div class="email-card"><div class="copy">{escape_html(empty_label)}</div></div>'
    cards = []
    for item in items[:10]:
        attention_action = ""
        if allow_attention_feedback:
            attention_action = (
                '<form method="post" action="/api/attention-feedback">'
                f'{attention_feedback_hidden_fields(item)}'
                '<input type="hidden" name="action" value="mark_needs_attention">'
                '<button class="action" type="submit">Mark needs attention</button>'
                '</form>'
            )
        cards.append(
            '<article class="email-card">'
            f'<h3>{escape_html(item.get("subject") or "(no subject)")}</h3>'
            f'<div class="meta">{escape_html(item.get("sender") or "(unknown sender)")}</div>'
            '<div class="pill-row">'
            f'<span class="pill">{escape_html(item.get("classification") or "Uncategorized")}</span>'
            f'<span class="pill">{escape_html(item.get("status_label") or item.get("status") or "")}</span>'
            '</div>'
            f'<a class="action" href="{escape_html(gmail_search_url(item))}" target="_blank" rel="noreferrer">Open in Gmail</a>'
            f'{attention_action}'
            '</article>'
        )
    return "".join(cards)

def render_dashboard_attention_cards(items: list[dict], empty_label: str) -> str:
    if not items:
        return f'<div class="email-card"><div class="copy">{escape_html(empty_label)}</div></div>'
    cards = []
    for item in items[:10]:
        mutation_label = "Attention pass: no Gmail changes" if item.get("gmail_mutation") == "none" else f'Gmail mutation: {item.get("gmail_mutation")}'
        feedback_state = item.get("feedback_state") or "unset"
        feedback_note = item.get("feedback_note") or ""
        corrected = ""
        if item.get("corrected_reason") or item.get("corrected_category"):
            corrected = (
                f'<div class="copy"><strong>Corrected:</strong> {escape_html(item.get("corrected_category") or "uncategorized")}'
                f' - {escape_html(item.get("corrected_reason") or "No corrected reason recorded.")}</div>'
            )
        feedback_note_html = (
            f'<div class="copy"><strong>Feedback note:</strong> {escape_html(feedback_note)}</div>'
            if feedback_note
            else ""
        )
        cards.append(
            '<article class="email-card attention-card">'
            f'<h3>{escape_html(item.get("subject") or "(no subject)")}</h3>'
            f'<div class="meta">{escape_html(item.get("sender") or "(unknown sender)")}</div>'
            '<div class="pill-row">'
            f'<span class="pill">{escape_html(item.get("category") or "uncategorized")}</span>'
            f'<span class="pill">{escape_html(item.get("surface_note") or item.get("level") or "")}</span>'
            f'<span class="pill">{escape_html(mutation_label)}</span>'
            f'<span class="pill">Feedback: {escape_html(feedback_state)}</span>'
            '</div>'
            f'<div class="copy"><strong>Reason:</strong> {escape_html(item.get("reason") or "No reason recorded.")}</div>'
            f'<div class="copy"><strong>Evidence:</strong> {escape_html(item.get("evidence") or "No evidence summary recorded.")}</div>'
            f'{feedback_note_html}'
            f'{corrected}'
            f'<div class="meta">{escape_html(item.get("source_context") or "Source message context unavailable")}</div>'
            '<div class="pill-row">'
            f'{attention_feedback_form(item, "good_catch", "Good catch")}'
            f'{attention_feedback_form(item, "not_attention", "Not attention")}'
            f'{attention_feedback_form(item, "wrong_reason", "Wrong reason")}'
            f'{attention_rule_proposal_form(item)}'
            '</div>'
            '</article>'
        )
    return "".join(cards)

def attention_feedback_form(item: dict, action: str, label: str) -> str:
    corrected_reason_input = (
        '<input class="feedback-input" name="corrected_reason" placeholder="Correct reason">'
        if action == "wrong_reason"
        else ""
    )
    return (
        '<form method="post" action="/api/attention-feedback">'
        f'{attention_feedback_hidden_fields(item)}'
        f'<input type="hidden" name="action" value="{escape_html(action)}">'
        f'{corrected_reason_input}'
        f'<button class="action" type="submit">{escape_html(label)}</button>'
        '</form>'
    )

def attention_feedback_hidden_fields(item: dict) -> str:
    fields = {
        "message_id": item.get("message_id", ""),
        "thread_id": item.get("thread_id", ""),
        "batch_id": item.get("batch_id", ""),
        "subject": item.get("subject", ""),
        "sender": item.get("sender", ""),
        "corrected_category": item.get("category", ""),
    }
    return "".join(
        f'<input type="hidden" name="{escape_html(key)}" value="{escape_html(value)}">'
        for key, value in fields.items()
    )

def attention_rule_proposal_form(item: dict) -> str:
    return (
        '<form method="post" action="/api/attention-rule-proposal/preview">'
        f'{attention_feedback_hidden_fields(item)}'
        '<button class="action" type="submit">Preview attention rule</button>'
        '</form>'
    )

def render_dashboard_changed_cards(items: list[dict]) -> str:
    if not items:
        return '<div class="email-card"><div class="copy">No tracked agent changes in this stored batch yet.</div></div>'
    cards = []
    for item in items:
        cards.append(
            '<article class="email-card">'
            f'<h3>{escape_html(item.get("subject") or "(no subject)")}</h3>'
            f'<div class="meta">{escape_html(item.get("sender") or "(unknown sender)")}</div>'
            f'<div class="pill-row"><span class="pill">{escape_html(item.get("change_group") or "Change")}</span></div>'
            f'<div class="copy">{escape_html(item.get("change_summary") or "")}</div>'
            f'<a class="action" href="{escape_html(gmail_search_url(item))}" target="_blank" rel="noreferrer">Open in Gmail</a>'
            '</article>'
        )
    return "".join(cards)

def render_dashboard_unsubscribe_cards(items: list[dict]) -> str:
    if not items:
        return '<div class="email-card"><div class="copy">No subscriptions are queued yet.</div></div>'
    cards = []
    for item in items:
        handoff_path = item.get("handoff_path") or "/unsubscribe-review"
        cards.append(
            '<article class="email-card">'
            f'<h3>{escape_html(item.get("display_name") or "(unknown list)")}</h3>'
            f'<div class="meta">{escape_html(item.get("sender") or "(unknown sender)")}</div>'
            f'<a class="action" href="{escape_html(handoff_path)}" target="_blank" rel="noreferrer">Open focused review</a>'
            '</article>'
        )
    return "".join(cards)

def render_dashboard_candidate_cards(items: list[dict]) -> str:
    if not items:
        return '<div class="email-card"><div class="copy">No candidate changes are waiting for review.</div></div>'
    cards = []
    for item in items:
        recommendation = item.get("latest_recommendation") or "Not yet evaluated"
        cards.append(
            '<article class="email-card">'
            f'<h3>{escape_html(item.get("title") or "(untitled candidate)")}</h3>'
            f'<div class="pill-row"><span class="pill">{escape_html(item.get("status") or "pending")}</span>'
            f'<span class="pill">{escape_html(recommendation)}</span></div>'
            '<div class="copy">Reviewed in the local evaluation lane before any durable promotion.</div>'
            '</article>'
        )
    return "".join(cards)

def escape_html(value: str) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

def gmail_search_url(item: dict) -> str:
    subject = " ".join(str(item.get("subject") or "").split())
    sender = str(item.get("sender") or "").strip()
    sender_query = sender
    if "<" in sender and ">" in sender:
        sender_query = sender.split("<", 1)[1].split(">", 1)[0].strip()
    query_parts = []
    if sender_query:
        query_parts.append(f"from:{sender_query}")
    if subject:
        query_parts.append(f'"{subject[:80]}"')
    query = " ".join(query_parts) or str(item.get("message_id") or "")
    return f"https://mail.google.com/mail/u/0/#search/{quote(query)}"

def server_origin(host_header: str) -> str:
    host = host_header.strip() or "127.0.0.1:8021"
    if host.startswith("http://") or host.startswith("https://"):
        return host
    return f"http://{host}"
