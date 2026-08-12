import tempfile
import unittest
import io
from pathlib import Path

from src.gmail_initial_classifier import (
    ReviewOnlyModelAssistedClassifier,
    configure_initial_classifier,
)
from src.gmail_automation import run_daily_gmail_automation
from src.gmail_writer import MockGmailLabelClient
from src.gmail_companion_ui import GmailCompanionApp, main as companion_main


class RecordingModelClient:
    model = "test-model"

    def __init__(self, response=None, error=None):
        self.response = response or {}
        self.error = error
        self.payloads = []

    def analyze_message(self, payload):
        self.payloads.append(payload)
        if self.error:
            raise self.error
        return self.response


class ReadRecordingGmailClient(MockGmailLabelClient):
    def __init__(self, message):
        super().__init__()
        self.message = message

    def list_messages(self, label_ids, max_results):
        self.calls.append(("list_messages", label_ids, max_results))
        return [self.message["id"]]

    def get_message(self, message_id):
        self.calls.append(("get_message", message_id))
        return self.message


class GmailInitialClassifierTests(unittest.TestCase):
    def message(self, **overrides):
        message = {
            "source": "gmail",
            "account_id": "founder-test",
            "message_id": "message-1",
            "sender": "Unknown <unknown@example.com>",
            "subject": "A hard to classify note",
            "date": "2026-08-12T10:00:00Z",
            "snippet": "Please take a look.",
            "body": "Please take a look when you can.",
            "gmail_label_ids": ["INBOX"],
        }
        message.update(overrides)
        return message

    def test_model_suggestion_is_review_only_with_compact_provenance(self):
        client = RecordingModelClient({
            "labels": ["personal", "reply-needed"],
            "confidence": "medium",
            "rationale": "A person appears to expect a response.",
            "unresolved": False,
        })
        classifier = ReviewOnlyModelAssistedClassifier(client)

        result = classifier.classify_messages("founder-test-batch-1", [self.message()])

        item = result["items"][0]
        self.assertEqual(item["applied_labels"], [])
        self.assertEqual(item["near_misses"], ["personal", "reply-needed"])
        self.assertEqual(item["review_state"], "pending")
        self.assertEqual(item["interpretation"], "A person appears to expect a response.")
        self.assertEqual(item["decision_provenance"], {
            "decision_source": "model",
            "llm_used": True,
            "llm_model": "test-model",
            "llm_confidence": "medium",
            "llm_abstained": False,
            "llm_failed": False,
        })
        self.assertNotIn("api_key", item["decision_provenance"])
        self.assertNotIn("body", item["decision_provenance"])
        self.assertEqual(client.payloads[0]["message_id"], "message-1")

    def test_deterministic_match_does_not_call_model_and_records_rules(self):
        client = RecordingModelClient(error=AssertionError("model should not run"))
        classifier = ReviewOnlyModelAssistedClassifier(client)

        result = classifier.classify_messages(
            "founder-test-batch-1",
            [self.message(
                sender="Store <promo@example.com>",
                subject="Last chance sale",
                snippet="Discount offer. Free shipping. Hurry.",
                body="Discount offer. Free shipping. Hurry.",
                gmail_label_ids=["INBOX", "CATEGORY_PROMOTIONS"],
                list_unsubscribe="<https://example.com/unsubscribe>",
            )],
        )

        item = result["items"][0]
        self.assertTrue(item["applied_labels"])
        self.assertEqual(item["decision_provenance"]["decision_source"], "rules")
        self.assertFalse(item["decision_provenance"]["llm_used"])
        self.assertEqual(client.payloads, [])

    def test_model_abstention_and_failure_remain_pending(self):
        abstaining = ReviewOnlyModelAssistedClassifier(RecordingModelClient({
            "labels": ["personal"],
            "confidence": "low",
            "rationale": "Not enough context.",
            "unresolved": True,
        }))
        failed = ReviewOnlyModelAssistedClassifier(
            RecordingModelClient(error=RuntimeError("provider unavailable"))
        )

        abstained_item = abstaining.classify_messages("batch-1", [self.message()])["items"][0]
        failed_item = failed.classify_messages("batch-2", [self.message()])["items"][0]

        self.assertEqual(abstained_item["applied_labels"], [])
        self.assertEqual(abstained_item["near_misses"], [])
        self.assertTrue(abstained_item["decision_provenance"]["llm_abstained"])
        self.assertEqual(failed_item["applied_labels"], [])
        self.assertTrue(failed_item["decision_provenance"]["llm_failed"])
        self.assertNotIn("provider unavailable", str(failed_item["decision_provenance"]))

    def test_configuration_is_explicit_and_missing_key_is_not_ready(self):
        disabled_classifier, disabled = configure_initial_classifier(
            "", env={}, client_factory=lambda _model: None
        )
        missing_classifier, missing = configure_initial_classifier(
            "test-model",
            env={},
            client_factory=lambda _model: (_ for _ in ()).throw(RuntimeError("missing key")),
        )

        self.assertIsNone(disabled_classifier)
        self.assertEqual(disabled["state"], "disabled")
        self.assertIsNone(missing_classifier)
        self.assertEqual(missing, {
            "state": "not-ready",
            "model": "test-model",
            "reason": "missing-api-key",
        })

    def test_configuration_builds_classifier_when_explicit_and_key_present(self):
        client = RecordingModelClient()
        classifier, status = configure_initial_classifier(
            "test-model",
            env={"EMAIL_AGENT_OPENAI_API_KEY": "secret"},
            client_factory=lambda model: client if model == "test-model" else None,
        )

        self.assertIsInstance(classifier, ReviewOnlyModelAssistedClassifier)
        self.assertEqual(status, {"state": "ready", "model": "test-model"})

    def test_daily_run_persists_model_suggestion_but_makes_zero_provider_writes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            client = ReadRecordingGmailClient({
                "id": "unknown-1",
                "threadId": "thread-unknown-1",
                "internalDate": "1786528800000",
                "snippet": "Please take a look.",
                "labelIds": ["INBOX"],
                "payload": {"headers": [
                    {"name": "From", "value": "Unknown <unknown@example.com>"},
                    {"name": "Subject", "value": "A hard to classify note"},
                    {"name": "Date", "value": "Wed, 12 Aug 2026 10:00:00 +0000"},
                ]},
            })
            classifier = ReviewOnlyModelAssistedClassifier(RecordingModelClient({
                "labels": ["personal"],
                "confidence": "medium",
                "rationale": "A personal note that needs confirmation.",
                "unresolved": False,
            }))

            result = run_daily_gmail_automation(
                account_id="founder-test",
                batch_size=1,
                storage_dir=storage_dir,
                gmail_client=client,
                classifier=classifier,
            )

            self.assertEqual(result.label_write_count, 0)
            self.assertEqual(result.inbox_removal_count, 0)
            self.assertEqual(len(result.unlabeled_exceptions), 1)
            item = result.unlabeled_exceptions[0]
            self.assertEqual(item["near_misses"], ["personal"])
            self.assertEqual(item["decision_provenance"]["llm_model"], "test-model")
            self.assertEqual(len(classifier._model_client.payloads), 1)
            self.assertEqual(
                [call[0] for call in client.calls],
                ["list_messages", "get_message"],
            )

    def test_companion_startup_option_is_forwarded_explicitly(self):
        captured = {}

        class FakeServer:
            server_port = 8021

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                return None

        def factory(host, port, storage_dir, **kwargs):
            captured.update(kwargs)
            return FakeServer()

        exit_code = companion_main(
            ["--classification-model", "test-model"],
            stdout=io.StringIO(),
            server_factory=factory,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["classification_model"], "test-model")

    def test_health_is_visibly_not_ready_for_misconfigured_model(self):
        app = GmailCompanionApp(
            Path("/tmp/example"),
            initial_classification_status={
                "state": "not-ready",
                "model": "test-model",
                "reason": "missing-api-key",
            },
        )

        health = app.health_status()

        self.assertEqual(health["status"], "not-ready")
        self.assertEqual(health["initial_classification"]["reason"], "missing-api-key")
        self.assertNotIn("key", health["initial_classification"])


if __name__ == "__main__":
    unittest.main()
