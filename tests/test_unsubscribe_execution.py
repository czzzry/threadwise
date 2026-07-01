import json
import tempfile
import unittest
from pathlib import Path

from src.unsubscribe_execution import UnsubscribeExecutor


class UnsubscribeExecutorTests(unittest.TestCase):
    def test_execute_selected_candidates_runs_one_click_https_and_writes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:promo@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:promo@example.com",
                                "display_name": "Promo Sender",
                                "sender": "Promo Sender <promo@example.com>",
                                "sender_address": "promo@example.com",
                                "decision_state": "selected",
                                "evidence_count": 2,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<https://example.com/unsub>",
                                "list_unsubscribe_post": "List-Unsubscribe=One-Click",
                            }
                        }
                    },
                    indent=2,
                )
            )
            requests: list[tuple[str, str, str | None]] = []
            executor = UnsubscribeExecutor(
                storage_dir=storage_dir,
                transport=lambda method, url, body=None: requests.append((method, url, body)) or {"status_code": 200},
            )

            preview = executor.preview_selected_candidates()
            result = executor.execute_selected_candidates()
            audit = json.loads((storage_dir / "unsubscribe_execution_audit.json").read_text())

            self.assertEqual(preview["ready_count"], 1)
            self.assertEqual(preview["unsupported_count"], 0)
            self.assertEqual(result["executed_count"], 1)
            self.assertEqual(result["failed_count"], 0)
            self.assertEqual(requests, [("POST", "https://example.com/unsub", "List-Unsubscribe=One-Click")])
            latest_attempt = audit["candidates"]["gmail:founder-test:promo@example.com"]["attempts"][-1]
            self.assertEqual(latest_attempt["status"], "executed")
            self.assertEqual(latest_attempt["method"], "one-click-post")

    def test_execute_selected_candidates_marks_mailto_only_candidate_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:newsletter@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:newsletter@example.com",
                                "display_name": "Newsletter",
                                "sender": "Newsletter <newsletter@example.com>",
                                "sender_address": "newsletter@example.com",
                                "decision_state": "selected",
                                "evidence_count": 1,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<mailto:unsubscribe@example.com>",
                                "list_unsubscribe_post": "",
                            }
                        }
                    },
                    indent=2,
                )
            )
            executor = UnsubscribeExecutor(storage_dir=storage_dir, transport=lambda method, url, body=None: {"status_code": 200})

            preview = executor.preview_selected_candidates()
            result = executor.execute_selected_candidates()
            audit = json.loads((storage_dir / "unsubscribe_execution_audit.json").read_text())

            self.assertEqual(preview["ready_count"], 0)
            self.assertEqual(preview["unsupported_count"], 1)
            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["unsupported_count"], 1)
            latest_attempt = audit["candidates"]["gmail:founder-test:newsletter@example.com"]["attempts"][-1]
            self.assertEqual(latest_attempt["status"], "unsupported")
            self.assertIn("mailto", latest_attempt["notes"])

    def test_linkedin_http_unsubscribe_preview_warns_about_provider_error_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:jobalerts-noreply@linkedin.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:jobalerts-noreply@linkedin.com",
                                "display_name": "LinkedIn Job Alerts",
                                "sender": "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
                                "sender_address": "jobalerts-noreply@linkedin.com",
                                "decision_state": "selected",
                                "evidence_count": 1,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<https://www.linkedin.com/comm/psettings/email-unsubscribe>",
                                "list_unsubscribe_post": "",
                            }
                        }
                    },
                    indent=2,
                )
            )

            preview = UnsubscribeExecutor(storage_dir=storage_dir).preview_selected_candidates()

            self.assertEqual(preview["ready_count"], 0)
            self.assertEqual(preview["unsupported_count"], 1)
            self.assertEqual(preview["candidates"][0]["status"], "unsupported")
            self.assertIn("signed-in error page", preview["candidates"][0]["notes"])


if __name__ == "__main__":
    unittest.main()
