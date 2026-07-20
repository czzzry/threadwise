

import json
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
        return f'<div class="empty-state">{escape_html(empty_label)}</div>'
    cards = []
    for item in items[:10]:
        attention_action = ""
        if allow_attention_feedback:
            attention_action = (
                '<form method="post" action="/api/attention-feedback">'
                f'{attention_feedback_hidden_fields(item)}'
                '<input type="hidden" name="action" value="mark_needs_attention">'
                '<button class="action action--secondary" type="submit">Mark needs attention</button>'
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
            f'<a class="action action--secondary" href="{escape_html(gmail_search_url(item))}" target="_blank" rel="noreferrer">Open in Gmail</a>'
            f'{attention_action}'
            '</article>'
        )
    return "".join(cards)

def render_dashboard_attention_cards(items: list[dict], empty_label: str) -> str:
    if not items:
        return f'<div class="empty-state">{escape_html(empty_label)}</div>'
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
        f'<button class="action action--secondary action--feedback" type="submit">{escape_html(label)}</button>'
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
        '<button class="action action--secondary action--feedback" type="submit">Preview attention rule</button>'
        '</form>'
    )

def render_dashboard_changed_cards(items: list[dict]) -> str:
    if not items:
        return '<div class="empty-state">No tracked agent changes in this stored batch yet.</div>'
    cards = []
    for item in items:
        cards.append(
            '<article class="email-card">'
            f'<h3>{escape_html(item.get("subject") or "(no subject)")}</h3>'
            f'<div class="meta">{escape_html(item.get("sender") or "(unknown sender)")}</div>'
            f'<div class="pill-row"><span class="pill">{escape_html(item.get("change_group") or "Change")}</span></div>'
            f'<div class="copy">{escape_html(item.get("change_summary") or "")}</div>'
            f'<a class="action action--secondary" href="{escape_html(gmail_search_url(item))}" target="_blank" rel="noreferrer">Open in Gmail</a>'
            '</article>'
        )
    return "".join(cards)

def render_dashboard_unsubscribe_cards(items: list[dict]) -> str:
    if not items:
        return '<div class="empty-state">No subscriptions are queued yet.</div>'
    cards = []
    for item in items:
        handoff_path = item.get("handoff_path") or "/unsubscribe-review"
        cards.append(
            '<article class="email-card subscription-row">'
            '<div class="subscription-identity">'
            '<span class="pill">Queued</span>'
            f'<h3>{escape_html(item.get("display_name") or "(unknown list)")}</h3>'
            f'<div class="meta">{escape_html(item.get("sender") or "(unknown sender)")}</div>'
            '</div>'
            f'<a class="action action--secondary" href="{escape_html(handoff_path)}" target="_blank" rel="noreferrer">Open focused review</a>'
            '</article>'
        )
    return "".join(cards)

def render_dashboard_candidate_cards(items: list[dict]) -> str:
    if not items:
        return '<div class="empty-state">No candidate changes are waiting for review.</div>'
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


def script_safe_json(value: object) -> str:
    return (
        json.dumps(value)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_install_page(*, origin: str, extension_path: str) -> str:
    safe_origin = escape_html(origin)
    safe_extension_path = escape_html(extension_path)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Threadwise Gmail Companion</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1d1a16;
      --muted: #6b6255;
      --line: #d9cfbf;
      --panel: #fffdf8;
      --soft: #f4ecdd;
      --accent: #0f766e;
      --accent-soft: #d8f3ef;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(180deg, #efe3cb 0%, #f6f0e4 42%, #f8f4eb 100%); color: var(--ink); }}
    main {{ max-width: 980px; margin: 0 auto; padding: 36px 20px 56px; display: grid; gap: 18px; }}
    .hero {{ background: var(--panel); border: 1px solid var(--line); border-radius: 22px; padding: 24px; box-shadow: 0 18px 40px rgba(29, 26, 22, 0.08); }}
    .eyebrow {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.72rem; }}
    h1 {{ margin: 10px 0 12px; font-size: 2rem; line-height: 1.05; }}
    p {{ line-height: 1.5; }}
    .grid {{ display: grid; gap: 18px; grid-template-columns: 1.2fr 0.8fr; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 18px; }}
    ol {{ margin: 10px 0 0; padding-left: 22px; }}
    li + li {{ margin-top: 8px; }}
    .path {{ margin-top: 12px; padding: 12px 14px; border-radius: 14px; border: 1px solid var(--line); background: #fcfaf5; font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; overflow-wrap: anywhere; }}
    .pill {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 0.84rem; }}
    .meta {{ color: var(--muted); }}
    @media (max-width: 820px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="eyebrow">Gmail Companion</div>
      <h1>Install the local Gmail sidebar once, then use it inside Gmail.</h1>
      <p>The old bookmark launcher path has been retired. The current setup is the local Brave extension plus the companion server on <span class="pill">{safe_origin}</span>.</p>
    </section>
    <section class="grid">
      <section class="card">
        <div class="eyebrow">Brave Setup</div>
        <ol>
          <li>Open <code>brave://extensions</code>.</li>
          <li>Turn on <strong>Developer mode</strong>.</li>
          <li>Choose <strong>Load unpacked</strong>.</li>
          <li>Select this folder:</li>
        </ol>
        <div class="path">{safe_extension_path}</div>
        <ol start="5">
          <li>Keep the companion server running at <code>{safe_origin}</code>.</li>
          <li>Open Gmail and refresh once.</li>
        </ol>
      </section>
      <section class="card">
        <div class="eyebrow">What You Should See</div>
        <p>A right-side panel inside Gmail that shows:</p>
        <ol>
          <li>the current email’s category</li>
          <li>whether it was auto-handled or still needs attention</li>
          <li>a short reason</li>
          <li>a compact view of today’s activity</li>
        </ol>
        <p class="meta">This page is now only for installation and troubleshooting. The product itself lives in Gmail.</p>
      </section>
    </section>
  </main>
</body>
</html>"""


def render_unsubscribe_review_page(details: list[dict], *, focus_list_key: str = "") -> str:
    rows_by_section: dict[str, list[str]] = {
        "ready": [],
        "queued": [],
        "manual": [],
    }
    for detail in details:
        preview = detail.get("preview") or {}
        action_html = _unsubscribe_action_html(preview)
        section_key = unsubscribe_section_key(detail, preview)
        rows_by_section[section_key].append(
            render_unsubscribe_row(
                detail,
                preview,
                action_html=action_html,
                focused=bool(focus_list_key and detail.get("list_key") == focus_list_key),
            )
        )

    sections_html = "".join(
        render_unsubscribe_section(key, title, description, rows_by_section[key])
        for key, title, description in [
            ("ready", "Ready now", "Supported one-click paths that are not queued yet."),
            ("queued", "Queued", "Subscriptions selected for later review."),
            ("manual", "Manual follow-up", "Subscriptions whose provider or mail flow needs a manual step."),
        ]
        if rows_by_section[key]
    )
    empty_html = (
        '<div class="empty-state">No unsubscribe candidates are stored yet.</div>'
        if not details
        else ""
    )
    group_counts = {key: len(rows) for key, rows in rows_by_section.items()}
    candidate_keys_json = script_safe_json(
        [detail.get("list_key") for detail in details if detail.get("list_key")]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Threadwise Unsubscribe Review</title>
  <style>
    body {{ margin:0; min-height:100vh; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at 18px 18px, rgba(36,24,18,.05) 2px, transparent 2px) 0 0 / 36px 36px, linear-gradient(135deg,#f7efe0 0%,#fdfaf2 52%,#e7f3ee 100%); color:#241812; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 34px; display:grid; gap:18px; }}
    .hero {{ background:#fff7e8; border:2px solid #241812; border-radius:18px; padding:18px; }}
    .hero-heading {{ display:flex; align-items:center; gap:12px; }}
    .brand-mark {{ width:42px; height:42px; border-radius:12px; border:1px solid #9e9486; flex:0 0 auto; background:#fff8df; }}
    .review-form,.section {{ display:grid; gap:18px; }}
    .unsubscribe-group {{ background:#fffdf7; border:1px solid #9e9486; border-radius:14px; padding:16px; }}
    .unsubscribe-list {{ display:grid; border-top:1px solid #d7cfbf; }}
    .unsubscribe-row {{ display:grid; grid-template-columns:32px minmax(190px,1.4fr) minmax(72px,.45fr) minmax(190px,1.2fr) minmax(170px,1fr) minmax(150px,.9fr); gap:12px; align-items:center; padding:12px 4px; border-bottom:1px solid #d7cfbf; }}
    .unsubscribe-row h3 {{ margin:0; font-size:.98rem; }}
    .identity-cell,.readiness-cell,.attempt-cell,.evidence-cell {{ min-width:0; display:grid; gap:4px; }}
    .address,.readiness-cell span,.attempt-cell span,.row-note,.row-link {{ color:#6b6255; font-size:.82rem; line-height:1.35; overflow-wrap:anywhere; word-break:break-word; }}
    .evidence-cell span {{ color:#6b6255; font-size:.76rem; }}
    .row-link {{ color:#315f55; font-weight:760; }}
    .eyebrow {{ color:#6b6255; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.14em; font-weight:820; }}
    h1,h2 {{ margin:8px 0 10px; }}
    h1 {{ font-size:2rem; line-height:1.05; }}
    p {{ line-height:1.45; }}
    .safety-note {{ border:1px solid #9e9486; border-radius:12px; background:#fffdf7; padding:10px 12px; color:#4d4134; }}
    .pill-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
    .pill {{ border:1px solid #9e9486; border-radius:999px; padding:6px 10px; background:#f1eadf; color:#241812; font-size:0.8rem; font-weight:760; }}
    .focused {{ border-color:#2eb67d; background:#f5fbfa; }}
    .focus-note {{ display:inline-flex; align-items:center; padding:6px 10px; border:2px solid #241812; border-radius:999px; background:#dff8ed; color:#09633c; font-size:0.82rem; font-weight:760; }}
    .batch-bar {{ position:sticky; bottom:12px; z-index:2; display:flex; align-items:center; justify-content:space-between; gap:12px; padding:12px 14px; border:1px solid #241812; border-radius:14px; background:#fffdf7; box-shadow:0 8px 24px rgba(36,24,18,.14); }}
    .batch-bar[hidden] {{ display:none; }}
    .save-selection {{ border:2px solid #241812; border-radius:10px; background:#2eb67d; color:#241812; padding:9px 12px; font-weight:800; box-shadow:3px 3px 0 #241812; }}
    .clear-selection {{ border:0; background:transparent; color:#5d5342; text-decoration:underline; font-weight:760; }}
    @media (max-width: 880px) {{
      main {{ padding:18px; }}
      .unsubscribe-row {{ grid-template-columns:28px minmax(0,1fr); align-items:start; }}
      .evidence-cell,.readiness-cell,.attempt-cell,.row-action-cell {{ grid-column:2; }}
      .batch-bar {{ flex-wrap:wrap; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-heading">
        <img class="brand-mark" src="/assets/brand/threadwise-app-icon.png" alt="" aria-hidden="true">
        <div>
          <div class="eyebrow">Unsubscribe Review</div>
          <h1>Subscription cleanup</h1>
        </div>
      </div>
      <p>Review subscription families and choose which ones to queue. Selection never executes an unsubscribe.</p>
      <div class="pill-row">
        <span class="pill">Ready now: {group_counts["ready"]}</span>
        <span class="pill">Queued: {group_counts["queued"]}</span>
        <span class="pill">Manual follow-up: {group_counts["manual"]}</span>
        <span class="pill">All candidates: {len(details)}</span>
      </div>
    </section>
    <aside class="safety-note" data-unsubscribe-safety-note>
      Queueing or clearing a selection does not execute an unsubscribe. Ready one-click HTTPS actions require a separate explicit confirmation. Manual mail or provider links leave Threadwise and do not count as execution.
    </aside>
    <form class="review-form" id="unsubscribe-selection-form">
      <section class="section">
        {sections_html}
        {empty_html}
      </section>
      <div class="batch-bar" data-unsubscribe-batch-bar {'hidden' if group_counts["queued"] < 1 else ''}>
        <strong><span data-unsubscribe-selected-count>{group_counts["queued"]}</span> selected</strong>
        <div>
          <button class="clear-selection" type="button" data-clear-unsubscribe-selection>Clear queued selections</button>
          <button class="save-selection" type="button" data-save-unsubscribe-selection>Save selection</button>
        </div>
        <span class="row-note" data-unsubscribe-selection-status aria-live="polite"></span>
      </div>
    </form>
  </main>
  <script>
    const candidateKeys = {candidate_keys_json};
    const selectionInputs = [...document.querySelectorAll('[data-unsubscribe-selection]')];
    const batchBar = document.querySelector('[data-unsubscribe-batch-bar]');
    const selectedCount = document.querySelector('[data-unsubscribe-selected-count]');
    const selectionStatus = document.querySelector('[data-unsubscribe-selection-status]');
    const saveSelectionButton = document.querySelector('[data-save-unsubscribe-selection]');
    const clearSelectionButton = document.querySelector('[data-clear-unsubscribe-selection]');
    let selectionSaveInFlight = false;
    let reloadScheduled = false;

    function selectedKeys() {{
      return selectionInputs.filter((input) => input.checked).map((input) => input.value);
    }}

    function updateBatchBar() {{
      const count = selectedKeys().length;
      selectedCount.textContent = String(count);
      batchBar.hidden = count < 1;
    }}

    async function persistSelection(keys) {{
      if (selectionSaveInFlight) {{
        return;
      }}
      selectionSaveInFlight = true;
      saveSelectionButton.disabled = true;
      clearSelectionButton.disabled = true;
      selectionStatus.textContent = 'Saving selection…';
      try {{
        const response = await fetch('/api/unsubscribe-candidates/selections', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            candidate_keys: candidateKeys,
            selected_candidate_keys: keys,
          }}),
        }});
        const payload = await response.json();
        if (!response.ok) {{
          selectionStatus.textContent = payload.error || 'Could not save selection.';
          return;
        }}
        selectionStatus.textContent = payload.acknowledgment;
        updateBatchBar();
        reloadScheduled = true;
        window.setTimeout(() => window.location.reload(), 350);
      }} catch (_error) {{
        selectionStatus.textContent = 'Could not reach Threadwise. Selection was not saved.';
      }} finally {{
        if (!reloadScheduled) {{
          selectionSaveInFlight = false;
          saveSelectionButton.disabled = false;
          clearSelectionButton.disabled = false;
        }}
      }}
    }}

    selectionInputs.forEach((input) => input.addEventListener('change', updateBatchBar));
    saveSelectionButton.addEventListener('click', () => {{
      persistSelection(selectedKeys());
    }});
    clearSelectionButton.addEventListener('click', () => {{
      selectionInputs.forEach((input) => {{ input.checked = false; }});
      persistSelection([]);
    }});
    updateBatchBar();
  </script>
</body>
</html>"""


def _unsubscribe_action_html(preview: dict) -> str:
    preview_url = str(preview.get("url") or "")
    if preview_url.startswith("mailto:"):
        return (
            f'<a class="row-link" href="{escape_html(preview_url)}">'
            'Open mail app · does not execute here</a>'
        )
    if preview_url.startswith("http") and preview.get("status") == "ready":
        return '<span class="row-note">Ready for a separately confirmed action</span>'
    if preview_url.startswith("http"):
        return (
            f'<a class="row-link" href="{escape_html(preview_url)}" target="_blank" rel="noreferrer">'
            'Open provider page · does not execute here</a>'
        )
    return ""
