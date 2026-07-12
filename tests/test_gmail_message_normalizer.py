import base64
import unittest

from src.gmail_message_normalizer import normalize_gmail_message


def _urlsafe(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")


class GmailMessageNormalizerTests(unittest.TestCase):
    def test_normalize_gmail_message_prefers_text_plain_payload_over_short_snippet(self) -> None:
        message = {
            "id": "gmail-live-001",
            "threadId": "thread-001",
            "internalDate": "1718784000000",
            "snippet": "Your single-use code is 123456.",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "Microsoft <account@example.com>"},
                    {"name": "Subject", "value": "Your single-use code"},
                    {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": _urlsafe(
                                "Hi Alex,\n\nYour single-use code is 123456.\nOnly enter this code on an official website."
                            )
                        },
                    }
                ],
            },
        }

        normalized = normalize_gmail_message("founder-test", message)

        self.assertEqual(normalized["snippet"], "Your single-use code is 123456.")
        self.assertIn("Only enter this code on an official website.", normalized["body"])
        self.assertNotEqual(normalized["body"], normalized["snippet"])

    def test_normalize_gmail_message_falls_back_to_stripped_html_when_plain_text_missing(self) -> None:
        message = {
            "id": "gmail-live-002",
            "threadId": "thread-002",
            "internalDate": "1718784000000",
            "snippet": "Big sale now live.",
            "payload": {
                "mimeType": "text/html",
                "headers": [
                    {"name": "From", "value": "Store <promotions@example.com>"},
                    {"name": "Subject", "value": "Weekend sale"},
                    {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                ],
                "body": {
                    "data": _urlsafe(
                        "<html><body><p>Weekend sale is live.</p><p>Use code <strong>SAVE10</strong>.</p></body></html>"
                    )
                },
            },
        }

        normalized = normalize_gmail_message("founder-test", message)

        self.assertEqual(normalized["snippet"], "Big sale now live.")
        self.assertIn("Weekend sale is live.", normalized["body"])
        self.assertIn("Use code SAVE10.", normalized["body"])

    def test_normalize_gmail_message_strips_link_sludge_from_html_preview_body(self) -> None:
        message = {
            "id": "gmail-live-004",
            "threadId": "thread-004",
            "internalDate": "1718784000000",
            "snippet": "Now available from an author you like.",
            "payload": {
                "mimeType": "text/html",
                "headers": [
                    {"name": "From", "value": "Audible <promotions@audible.com>"},
                    {"name": "Subject", "value": "Membership Now"},
                    {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                ],
                "body": {
                    "data": _urlsafe(
                        "<html><body>"
                        "<p>Now available from an author you like</p>"
                        "<p>A new listen to get excited about.</p>"
                        "<p>The Wealth of Nations by Adam Smith</p>"
                        "<p>https://www.audible.com/account/overview</p>"
                        "<p>Privacy Notice</p>"
                        "<p>This email was sent to alex@example.com.</p>"
                        "</body></html>"
                    )
                },
            },
        }

        normalized = normalize_gmail_message("founder-test", message)

        self.assertIn("Now available from an author you like", normalized["body"])
        self.assertIn("A new listen to get excited about.", normalized["body"])
        self.assertNotIn("https://www.audible.com/account/overview", normalized["body"])
        self.assertNotIn("This email was sent to", normalized["body"])

    def test_normalize_gmail_message_uses_fallback_values_when_payload_has_no_extractable_text(self) -> None:
        normalized = normalize_gmail_message(
            "founder-test",
            {
                "id": "gmail-live-003",
                "payload": {"headers": []},
            },
            fallback_message={
                "subject": "Fallback subject",
                "body": "Fallback body",
                "snippet": "Fallback snippet",
                "date": "2024-06-19T08:00:00Z",
            },
        )

        self.assertEqual(normalized["snippet"], "Fallback snippet")
        self.assertEqual(normalized["body"], "Fallback body")


if __name__ == "__main__":
    unittest.main()
