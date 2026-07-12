import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time
import json
from pathlib import Path
import urllib.error
import urllib.request


class SetupError(Exception):
    pass


class LiveOutlookMailBrowserClient:
    def __init__(
        self,
        debug_base_url: str = "http://127.0.0.1:9222",
        page_url_substring: str = "outlook.live.com/mail",
        target_lister: Callable[[], list[dict]] | None = None,
        row_loader: Callable[[str, int], list[dict] | Awaitable[list[dict]]] | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._debug_base_url = debug_base_url.rstrip("/")
        self._page_url_substring = page_url_substring
        self._target_lister = target_lister or self._list_targets_from_debug_endpoint
        self._row_loader = row_loader or _load_rows_via_cdp
        self._now_fn = now_fn or (lambda: datetime.now(tz=UTC))
        self._cached_messages: dict[str, dict] = {}

    def list_messages(self, max_results: int) -> list[str]:
        targets = self._target_lister()
        target = next((item for item in targets if self._page_url_substring in item.get("url", "")), None)
        if target is None:
            raise SetupError(
                "No signed-in Outlook inbox tab was found on the local browser debug port. "
                "Launch Brave with --remote-debugging-port=9222 and sign in to Outlook Web first."
            )

        rows = self._load_rows(target["webSocketDebuggerUrl"], max_results)
        if not rows:
            return []

        self._cached_messages = {
            message["id"]: message
            for message in (self._message_from_row(row) for row in rows)
        }
        return list(self._cached_messages)[:max_results]

    def get_message(self, message_id: str) -> dict:
        if message_id not in self._cached_messages:
            raise SetupError(
                f"Outlook browser message {message_id} is not available in the current cached inbox rows. "
                "Run list_messages first from the same signed-in browser session."
            )
        return self._cached_messages[message_id]

    def _list_targets_from_debug_endpoint(self) -> list[dict]:
        try:
            raw = urllib.request.urlopen(f"{self._debug_base_url}/json").read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise SetupError(
                "Could not reach the local browser debug port. "
                "Make sure Brave is running with --remote-debugging-port=9222."
            ) from exc
        return json.loads(raw)

    def _load_rows(self, web_socket_debugger_url: str, max_results: int) -> list[dict]:
        result = self._row_loader(web_socket_debugger_url, max_results)
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result

    def _message_from_row(self, row: dict) -> dict:
        lines = [line.strip() for line in row.get("lines", []) if line.strip()]
        sender = lines[1] if len(lines) >= 2 else ""
        subject = lines[2] if len(lines) >= 3 else ""
        preview = lines[3] if len(lines) >= 4 else ""
        received_label = lines[4] if len(lines) >= 5 else ""
        received_at = _normalize_received_at(received_label, now=self._now_fn())
        body = preview or subject or sender
        snippet = body[:160]
        return {
            "id": row["message_id"],
            "mailbox": "inbox",
            "sender": sender,
            "subject": subject,
            "date": received_at,
            "snippet": snippet,
            "body": body,
            "list_unsubscribe": None,
            "precedence": "",
        }


def _normalize_received_at(label: str, now: datetime) -> str:
    text = label.strip()
    if not text:
        return now.isoformat().replace("+00:00", "Z")
    try:
        if ":" in text and ("AM" in text or "PM" in text):
            parsed_time = datetime.strptime(text, "%I:%M %p").time()
            today = datetime.combine(now.date(), parsed_time, tzinfo=UTC)
            return today.isoformat().replace("+00:00", "Z")
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            parsed_date = date.fromisoformat(text)
            midnight = datetime.combine(parsed_date, time.min, tzinfo=UTC)
            return midnight.isoformat().replace("+00:00", "Z")
    except ValueError:
        pass
    return now.isoformat().replace("+00:00", "Z")


async def _load_rows_via_cdp(web_socket_debugger_url: str, max_results: int) -> list[dict]:
    try:
        import websockets
    except ImportError as exc:
        raise SetupError(
            "The Python websockets package is required for the Outlook browser fetch path."
        ) from exc

    async with websockets.connect(web_socket_debugger_url, max_size=10_000_000) as ws:
        next_id = 1

        async def send(method: str, params: dict | None = None) -> dict:
            nonlocal next_id
            message_id = next_id
            next_id += 1
            await ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
            while True:
                payload = json.loads(await ws.recv())
                if payload.get("id") != message_id:
                    continue
                if "error" in payload:
                    raise SetupError(f"Outlook browser CDP call failed: {payload['error']}")
                return payload.get("result", {})

        await send("Runtime.enable")

        async def load_visible_rows() -> list[dict]:
            expression = f"""
(() => {{
  const rows = Array.from(document.querySelectorAll('[data-convid]')).slice(0, {max_results});
  return rows.map((el) => ({{
    message_id: el.id,
    conversation_id: el.getAttribute('data-convid'),
    aria_label: el.getAttribute('aria-label'),
    lines: (el.innerText || '')
      .split('\\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 5)
  }}));
}})()
"""
            result = await send(
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )
            return result["result"]["value"]

        async def select_mail_tab(tab_name: str) -> bool:
            result = await send(
                "Runtime.evaluate",
                {
                    "expression": f"""
(() => {{
  const tab = Array.from(document.querySelectorAll('[role="tab"]'))
    .find((el) => /{tab_name}/i.test((el.textContent || '').trim()));
  if (!tab) {{
    return false;
  }}
  if (tab.getAttribute('aria-selected') === 'true') {{
    return true;
  }}
  tab.click();
  return true;
}})()
""",
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )
            return bool(result["result"]["value"])

        async def scroll_for_more_rows() -> bool:
            result = await send(
                "Runtime.evaluate",
                {
                    "expression": """
(() => {
  const rows = Array.from(document.querySelectorAll('[data-convid]'));
  const lastRow = rows.at(-1);
  if (!lastRow) {
    return false;
  }
  let scroller = lastRow.parentElement;
  while (scroller) {
    const style = window.getComputedStyle(scroller);
    const canScroll = (style.overflowY === 'auto' || style.overflowY === 'scroll')
      && scroller.scrollHeight > scroller.clientHeight;
    if (canScroll) {
      const previousTop = scroller.scrollTop;
      const step = Math.max(120, Math.floor(scroller.clientHeight * 0.35));
      scroller.scrollTop = Math.min(scroller.scrollTop + step, scroller.scrollHeight);
      return scroller.scrollTop !== previousTop;
    }
    scroller = scroller.parentElement;
  }
  lastRow.scrollIntoView({ block: 'end' });
  return true;
})()
""",
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )
            return bool(result["result"]["value"])

        async def reset_scroller_to_top() -> None:
            await send(
                "Runtime.evaluate",
                {
                    "expression": """
(() => {
  const firstRow = document.querySelector('[data-convid]');
  if (!firstRow) {
    return false;
  }
  let scroller = firstRow.parentElement;
  while (scroller) {
    const style = window.getComputedStyle(scroller);
    const canScroll = (style.overflowY === 'auto' || style.overflowY === 'scroll')
      && scroller.scrollHeight > scroller.clientHeight;
    if (canScroll) {
      scroller.scrollTop = 0;
      return true;
    }
    scroller = scroller.parentElement;
  }
  return false;
})()
""",
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )

        async def wait_for_ui() -> None:
            await send(
                "Runtime.evaluate",
                {
                    "expression": """
new Promise((resolve) => {
  setTimeout(() => resolve(true), 750);
})
""",
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )

        async def collect_rows_for_current_tab(
            seen_rows: dict[str, dict],
            remaining_limit: int,
        ) -> None:
            stagnant_rounds = 0
            await reset_scroller_to_top()
            await wait_for_ui()

            # Outlook uses a virtualized list. Keep going until the scroller stops
            # moving rather than trusting a small fixed iteration count.
            for _ in range(max(200, remaining_limit * 2)):
                visible_rows = await load_visible_rows()
                previous_count = len(seen_rows)
                for row in visible_rows:
                    message_id = row.get("message_id")
                    if message_id and message_id not in seen_rows:
                        seen_rows[message_id] = row

                if len(seen_rows) >= max_results:
                    return

                if len(seen_rows) == previous_count:
                    stagnant_rounds += 1
                else:
                    stagnant_rounds = 0

                if stagnant_rounds >= 5:
                    return

                if not await scroll_for_more_rows():
                    return

                await wait_for_ui()

        seen_rows: dict[str, dict] = {}

        for tab_name in ("Focused", "Other"):
            selected = await select_mail_tab(tab_name)
            if not selected:
                continue
            await wait_for_ui()
            await collect_rows_for_current_tab(seen_rows, max_results - len(seen_rows))
            if len(seen_rows) >= max_results:
                break

        return list(seen_rows.values())[:max_results]
