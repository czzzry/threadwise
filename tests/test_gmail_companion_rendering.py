import json
import unittest

from src.gmail_companion_rendering import (
    render_install_page,
    render_unsubscribe_review_page,
)


class GmailCompanionRenderingTests(unittest.TestCase):
    def test_install_page_escapes_runtime_values(self) -> None:
        page = render_install_page(
            origin='http://127.0.0.1:8021/<script>alert("host")</script>',
            extension_path='/tmp/<script>alert("path")</script>',
        )

        self.assertIn("Load unpacked", page)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;alert", page)

    def test_unsubscribe_page_owns_grouping_focus_and_script_safe_candidate_keys(self) -> None:
        hostile_key = "gmail:test:</script><script>window.pwned=1</script>&@example.com"
        page = render_unsubscribe_review_page(
            [
                {
                    "list_key": hostile_key,
                    "display_name": "Hostile fixture",
                    "sender": "fixture@example.com",
                    "decision_state": "selected",
                    "evidence_count": 1,
                    "latest_execution": None,
                    "preview": {
                        "status": "ready",
                        "method": "https_one_click",
                        "notes": "Ready",
                        "url": "https://example.test/unsubscribe",
                    },
                }
            ],
            focus_list_key=hostile_key,
        )

        candidate_script = page.split("const candidateKeys = ", 1)[1].split(";", 1)[0]
        self.assertEqual(json.loads(candidate_script), [hostile_key])
        self.assertNotIn("</script><script>window.pwned", candidate_script)
        self.assertIn('data-unsubscribe-group="queued"', page)
        self.assertIn("Opened from inbox", page)
        self.assertIn("Ready for a separately confirmed action", page)


if __name__ == "__main__":
    unittest.main()
