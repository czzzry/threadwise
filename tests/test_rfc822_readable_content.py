import unittest
from email import message_from_bytes

from src.rfc822_readable_content import extract_readable_content


class Rfc822ReadableContentTests(unittest.TestCase):
    def test_prefers_plain_text_over_html(self) -> None:
        message = message_from_bytes(
            b"Content-Type: multipart/alternative; boundary=choice\r\n"
            b"\r\n"
            b"--choice\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"\r\n"
            b"Plain answer\r\n"
            b"--choice\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"\r\n"
            b"<p>HTML answer</p>\r\n"
            b"--choice--\r\n"
        )

        self.assertEqual(extract_readable_content(message), "Plain answer")

    def test_decodes_declared_charset(self) -> None:
        message = message_from_bytes(
            "Content-Type: text/plain; charset=iso-8859-1\r\n\r\ncafé déjà".encode("iso-8859-1")
        )

        self.assertEqual(extract_readable_content(message), "café déjà")

    def test_html_omits_non_readable_payload_and_survives_unclosed_head(self) -> None:
        message = message_from_bytes(
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"\r\n"
            b"<html><head><style>hidden style</style><script>hidden script</script>"
            b"<body><p>Visible content survives.</p></body></html>"
        )

        self.assertEqual(extract_readable_content(message), "Visible content survives.")

    def test_html_resumes_after_nested_markup_inside_an_ignored_element(self) -> None:
        message = message_from_bytes(
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"\r\n"
            b"<noscript><div>Hidden fallback<br>still hidden</div></noscript>"
            b"<p>Visible content follows.</p>"
        )

        self.assertEqual(extract_readable_content(message), "Visible content follows.")

    def test_applies_optional_line_and_character_limits_after_sanitizing(self) -> None:
        message = message_from_bytes(
            ("Content-Type: text/plain; charset=utf-8\r\n\r\n" + "\r\n".join(
                f"Context line {index}" for index in range(1, 14)
            )).encode()
        )

        content = extract_readable_content(message, max_lines=8, max_chars=60)

        self.assertEqual(content.count("\n"), 4)
        self.assertEqual(len(content), 60)
        self.assertTrue(content.startswith("Context line 1\nContext line 2"))


if __name__ == "__main__":
    unittest.main()
