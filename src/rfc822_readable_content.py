import re
from email.message import Message
from html import unescape
from html.parser import HTMLParser


def extract_readable_content(
    message: Message,
    *,
    max_lines: int | None = None,
    max_chars: int | None = None,
) -> str:
    """Extract readable text from an RFC822 message.

    MIME traversal, charset decoding, and HTML cleanup stay consistent across
    provider adapters. Providers may retain their presentation policy through
    optional line and character limits.
    """
    plain_text = _extract_first_part_text(message, "text/plain")
    if plain_text:
        return _shape_text(plain_text, max_lines=max_lines, max_chars=max_chars)

    html_text = _extract_first_part_text(message, "text/html")
    if html_text:
        return _shape_text(
            _html_to_text(html_text),
            max_lines=max_lines,
            max_chars=max_chars,
        )

    return ""


def _extract_first_part_text(message: Message, content_type: str) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == content_type:
                return _decode_part(part)
        return ""

    if message.get_content_type() != content_type:
        return ""

    return _decode_part(message)


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace").strip()
    except LookupError:
        return payload.decode("utf-8", errors="replace").strip()


def _shape_text(value: str, *, max_lines: int | None, max_chars: int | None) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        lines.append(line)
        if max_lines is not None and len(lines) >= max_lines:
            break

    shaped = "\n".join(lines)
    return shaped[:max_chars] if max_chars is not None else shaped


def _html_to_text(value: str) -> str:
    parser = _HtmlTextExtractor()
    parser.feed(value)
    parser.close()
    return re.sub(r"\s+([.,!?;:])", r"\1", parser.text()).strip()


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._block_tags = {
            "p", "div", "br", "li", "ul", "ol", "section", "tr", "td",
            "h1", "h2", "h3", "h4",
        }
        # Do not suppress the entire <head>: malformed real-world email often
        # places visible body content before a closing </head>.
        self._ignored_tags = {"style", "script", "template", "noscript"}
        self._void_tags = {
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        }
        self._ignored_stack: list[str] = []

    def handle_data(self, data: str) -> None:
        if self._ignored_stack:
            return
        cleaned = unescape(data).strip()
        if cleaned:
            if (
                self._chunks
                and self._chunks[-1]
                and self._chunks[-1][-1].isalnum()
                and cleaned[0].isalnum()
            ):
                self._chunks.append(" ")
            self._chunks.append(cleaned)

    def handle_starttag(self, tag: str, attrs) -> None:
        del attrs
        if self._ignored_stack:
            if tag not in self._void_tags:
                self._ignored_stack.append(tag)
            return
        if tag in self._ignored_tags:
            self._ignored_stack.append(tag)
            return
        if tag in self._block_tags:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._ignored_stack:
            if tag in self._ignored_stack:
                while self._ignored_stack:
                    opened_tag = self._ignored_stack.pop()
                    if opened_tag == tag:
                        break
            return
        if tag in self._block_tags:
            self._chunks.append("\n")

    def text(self) -> str:
        return "".join(self._chunks)
