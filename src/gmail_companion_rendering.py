

def unsubscribe_section_key(detail: dict, preview: dict) -> str:
    if detail.get("decision_state") == "selected":
        return "selected"
    if preview.get("status") == "ready":
        return "ready"
    if preview.get("status") == "unsupported":
        return "manual"
    return "other"

def render_unsubscribe_section(title: str, description: str, cards: list[str]) -> str:
    return (
        '<section class="hero">'
        f'<div class="eyebrow">{escape_html(title)}</div>'
        f'<h2>{escape_html(title)}</h2>'
        f'<p>{escape_html(description)}</p>'
        f'<div class="grid">{"".join(cards)}</div>'
        '</section>'
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

def render_dashboard_email_cards(items: list[dict], empty_label: str) -> str:
    if not items:
        return f'<div class="email-card"><div class="copy">{escape_html(empty_label)}</div></div>'
    cards = []
    for item in items[:10]:
        cards.append(
            '<article class="email-card">'
            f'<h3>{escape_html(item.get("subject") or "(no subject)")}</h3>'
            f'<div class="meta">{escape_html(item.get("sender") or "(unknown sender)")}</div>'
            '<div class="pill-row">'
            f'<span class="pill">{escape_html(item.get("classification") or "Uncategorized")}</span>'
            f'<span class="pill">{escape_html(item.get("status_label") or item.get("status") or "")}</span>'
            '</div>'
            '</article>'
        )
    return "".join(cards)

def render_dashboard_changed_cards(items: list[dict]) -> str:
    if not items:
        return '<div class="email-card"><div class="copy">No tracked agent changes in this stored batch yet.</div></div>'
    cards = []
    for item in items:
        cards.append(
            '<article class="email-card">'
            f'<h3>{escape_html(item.get("subject") or "(no subject)")}</h3>'
            f'<div class="meta">{escape_html(item.get("sender") or "(unknown sender)")}</div>'
            f'<div class="copy">{escape_html(item.get("change_summary") or "")}</div>'
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

def escape_html(value: str) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

def server_origin(host_header: str) -> str:
    host = host_header.strip() or "127.0.0.1:8021"
    if host.startswith("http://") or host.startswith("https://"):
        return host
    return f"http://{host}"
