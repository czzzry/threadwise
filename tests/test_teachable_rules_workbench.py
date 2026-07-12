import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.teachable_rule_memory import TeachableRule, TeachableRuleMemory, matching_rules_for_message, parse_teaching_instruction
from src.teachable_rules_workbench import TeachableRulesWorkbenchApp, classify_with_teachable_rules, main


class TeachableRuleMemoryTests(unittest.TestCase):
    def test_parse_recruiter_instruction_into_job_related_rule(self) -> None:
        rule = parse_teaching_instruction(
            "anything from recruiters, Ashby, Greenhouse, or Lever should be job-related and kept visible"
        )

        self.assertEqual(rule.label, "job-related")
        self.assertTrue(rule.keep_visible)
        self.assertEqual(rule.terms, ("recruiters", "recruiter", "ashby", "greenhouse", "lever"))

    def test_saved_instruction_persists_as_local_rule_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            rules_path = Path(temp_dir) / "prototype_rules.json"
            memory = TeachableRuleMemory(rules_path)

            rule = memory.save_instruction("anything from Ashby should be job-related and kept visible")

            self.assertTrue(rules_path.exists())
            self.assertEqual(memory.list_rules()[0].id, rule.id)
            payload = json.loads(rules_path.read_text())
            self.assertEqual(payload["status"], "PROTOTYPE - local teachable classification memory")

    def test_shadow_rule_matching_uses_family_not_generic_term_overlap(self) -> None:
        rule = TeachableRule(
            id="shadow-gmail-001",
            instruction="Anything from no-reply@amazon.de with subject like 'your return for amazon order #-#-#' should be receipt-billing.",
            label="receipt-billing",
            terms=("no-reply@amazon.de", "your return for amazon order #-#-#", "order"),
            keep_visible=False,
            created_at="2026-06-28T00:00:00Z",
            providers=("gmail",),
            source_examples=(
                {
                    "sender": '"Amazon.de" <no-reply@amazon.de>',
                    "subject": "Your return for Amazon order 305-0960012-3218757",
                },
            ),
        )

        exact_match = matching_rules_for_message(
            {
                "provider": "gmail",
                "sender": '"Amazon.de" <no-reply@amazon.de>',
                "subject": "Your return for Amazon order 123-4567890-1111111",
                "snippet": "",
                "body": "",
            },
            [rule],
        )
        near_family_with_generic_term = matching_rules_for_message(
            {
                "provider": "gmail",
                "sender": '"Amazon.de" <order-update@amazon.de>',
                "subject": 'Item cancelled successfully: "Wessper Water Filter Jug..."',
                "snippet": "",
                "body": "Your order was cancelled.",
            },
            [rule],
        )

        self.assertEqual(len(exact_match), 1)
        self.assertEqual(near_family_with_generic_term, [])

    def test_non_shadow_rule_still_matches_on_any_saved_term(self) -> None:
        rule = parse_teaching_instruction(
            "anything from recruiters, Ashby, Greenhouse, or Lever should be job-related and kept visible"
        )

        matched = matching_rules_for_message(
            {
                "provider": "gmail",
                "sender": "Example <noreply@example.com>",
                "subject": "Update from Greenhouse",
                "snippet": "",
                "body": "",
            },
            [rule],
        )

        self.assertEqual(len(matched), 1)


class TeachableRulesWorkbenchTests(unittest.TestCase):
    def test_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/teach_email_agent_rules.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("teaching EmailAgent classification", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_prints_local_url(self) -> None:
        stdout = io.StringIO()
        fake_server = _FakeServer(server_port=45123)

        exit_code = main(
            ["--fixtures-dir", "/tmp/example", "--rules-path", "/tmp/rules.json"],
            stdout=stdout,
            server_factory=lambda host, port, fixtures_dir, rules_path: fake_server,
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(fake_server.served)
        self.assertTrue(fake_server.closed)
        self.assertIn("http://127.0.0.1:45123", stdout.getvalue())

    def test_classification_changes_after_saved_rule_matches_sample_sender(self) -> None:
        fixtures_dir = Path(__file__).resolve().parent.parent / "examples" / "prototype_teachable_workbench"
        messages = json.loads((fixtures_dir / "teachable-samples.json").read_text())["messages"]
        baseline_items = classify_with_teachable_rules(fixtures_dir, messages, [])
        ashby_baseline = next(item for item in baseline_items if item["message_id"] == "teach-001")
        self.assertEqual(ashby_baseline["applied_labels"], [])

        rule = parse_teaching_instruction(
            "anything from recruiters, Ashby, Greenhouse, or Lever should be job-related and kept visible"
        )
        taught_items = classify_with_teachable_rules(fixtures_dir, messages, [rule])
        ashby_taught = next(item for item in taught_items if item["message_id"] == "teach-001")

        self.assertEqual(ashby_taught["applied_labels"], ["EA/Work"])
        self.assertEqual(ashby_taught["matched_rules"][0]["id"], "teach-001")
        self.assertIn("Matched saved teaching rule", ashby_taught["interpretation"])

    def test_app_api_saves_instruction_and_returns_rerun_state_with_rule_match(self) -> None:
        fixtures_dir = Path(__file__).resolve().parent.parent / "examples" / "prototype_teachable_workbench"
        with tempfile.TemporaryDirectory() as temp_dir:
            app = TeachableRulesWorkbenchApp(fixtures_dir=fixtures_dir, rules_path=Path(temp_dir) / "rules.json")

            status, payload = app.handle_api_request(
                "POST",
                "/api/instructions",
                {"instruction": "anything from Ashby should be job-related and kept visible"},
            )

            self.assertEqual(status, 200)
            ashby_item = next(item for item in payload["items"] if item["message_id"] == "teach-001")
            self.assertEqual(ashby_item["applied_labels"], ["EA/Work"])
            self.assertEqual(ashby_item["matched_rules"][0]["terms"], ["ashby"])
            self.assertIn("rules.json", payload["rules_path"])

    def test_rendered_page_contains_teaching_controls_and_rule_match_language(self) -> None:
        fixtures_dir = Path(__file__).resolve().parent.parent / "examples" / "prototype_teachable_workbench"
        with tempfile.TemporaryDirectory() as temp_dir:
            app = TeachableRulesWorkbenchApp(fixtures_dir=fixtures_dir, rules_path=Path(temp_dir) / "rules.json")
            page = app.render_page()

            self.assertIn("EmailAgent Teaching Prototype", page)
            self.assertIn("Save instruction", page)
            self.assertIn("Rerun classification", page)
            self.assertIn("Rule matched", page)


class _FakeServer:
    def __init__(self, server_port: int) -> None:
        self.server_port = server_port
        self.served = False
        self.closed = False

    def serve_forever(self) -> None:
        self.served = True

    def server_close(self) -> None:
        self.closed = True


if __name__ == "__main__":
    unittest.main()
