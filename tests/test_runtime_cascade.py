import json
import tempfile
import unittest
from pathlib import Path

from src.runtime_cascade import build_runtime_cascade_report
from src.teachable_rule_memory import TeachableRule


class FakeRuntimeCascadeClient:
    def __init__(self) -> None:
        self.calls = []

    def analyze_message(self, payload: dict) -> dict:
        self.calls.append(payload)
        if payload["sender"] == "Utopia":
            return {
                "labels": ["newsletter"],
                "confidence": "medium",
                "rationale": "Recurring game-update notifications.",
                "unresolved": False,
            }
        return {
            "labels": [],
            "confidence": "low",
            "rationale": "Still unclear.",
            "unresolved": True,
        }


class RuntimeCascadeTests(unittest.TestCase):
    def test_runtime_cascade_distinguishes_deterministic_memory_llm_and_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            outlook_dir = root / "outlookmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": '"Acme Unknown" <alerts@acme-unknown.test>',
                        "subject": "Quarterly widget digest",
                        "snippet": "Digest.",
                        "body": "Digest.",
                    },
                    {
                        "message_id": "g2",
                        "sender": "Mystery Sender",
                        "subject": "Mystery note",
                        "snippet": "Unknown.",
                        "body": "Unknown.",
                    },
                ],
            )
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Security Team",
                        "subject": "Your verification code",
                        "snippet": "verification code",
                        "body": "Use this verification code to sign-in.",
                    },
                    {
                        "message_id": "o2",
                        "sender": "Utopia",
                        "subject": "Utopia Age 113 - Age of Merry Mayhems",
                        "snippet": "Update.",
                        "body": "Update.",
                    },
                ],
            )
            rules = [
                TeachableRule(
                    id="shadow-gmail-001",
                    instruction="Anything from alerts@acme-unknown.test with subject like 'quarterly widget digest' should be newsletter.",
                    label="newsletter",
                    terms=("alerts@acme-unknown.test", "quarterly widget digest"),
                    keep_visible=False,
                    created_at="2026-06-28T00:00:00Z",
                    providers=("gmail",),
                    enabled=True,
                    source_examples=(
                        {
                            "sender": '"Acme Unknown" <alerts@acme-unknown.test>',
                            "subject": "Quarterly widget digest",
                        },
                    ),
                )
            ]
            cluster_pack = {
                "preference_reviews": [
                    {
                        "provider": "outlookmail",
                        "sender_key": "utopia",
                        "memory_seed": {
                            "cluster_policy_key": "outlookmail:utopia",
                            "llm_prompt_context": "User likely treats these as low-priority game updates.",
                        },
                    }
                ]
            }
            llm_client = FakeRuntimeCascadeClient()

            report = build_runtime_cascade_report(
                [("gmail", gmail_dir), ("outlookmail", outlook_dir)],
                extra_rules=rules,
                cluster_decision_pack=cluster_pack,
                llm_client=llm_client,
                llm_limit=5,
            )

            self.assertEqual(report["summary"]["message_count"], 4)
            self.assertEqual(report["summary"]["deterministic_count"], 1)
            self.assertEqual(report["summary"]["accepted_memory_count"], 1)
            self.assertEqual(report["summary"]["llm_escalation_count"], 1)
            self.assertEqual(report["summary"]["unresolved_count"], 1)
            self.assertEqual(report["summary"]["memory_context_hit_count"], 1)
            self.assertEqual(report["summary"]["safety_counts"]["security-sensitive"], 1)
            self.assertEqual(report["providers"]["outlookmail"]["llm_call_count"], 1)
            gmail_outcomes = report["providers"]["gmail"]["outcomes"]
            deterministic = next(item for item in gmail_outcomes if item["stage"] == "accepted-memory")
            self.assertEqual(deterministic["decision_provenance"]["decision_source"], "accepted-memory")
            self.assertEqual(deterministic["decision_provenance"]["matched_rule_ids"], ["shadow-gmail-001"])
            self.assertEqual(deterministic["decision"]["actionability"], "ignore")
            outlook_outcomes = report["providers"]["outlookmail"]["outcomes"]
            security_outcome = next(item for item in outlook_outcomes if item["stage"] == "deterministic")
            self.assertEqual(security_outcome["decision_provenance"]["decision_source"], "deterministic")
            self.assertEqual(security_outcome["decision"]["risk_state"], "security-sensitive")
            self.assertEqual(security_outcome["decision"]["safety_lane"], "security-sensitive")
            self.assertTrue(security_outcome["decision"]["requires_caution"])
            utopia_outcome = next(item for item in outlook_outcomes if item["sender"] == "Utopia")
            self.assertEqual(utopia_outcome["decision_provenance"]["decision_source"], "llm-escalation")
            self.assertEqual(
                utopia_outcome["decision_provenance"]["retrieved_memory_keys"],
                ["outlookmail:utopia"],
            )
            self.assertTrue(utopia_outcome["decision_provenance"]["llm_used"])
            self.assertEqual(utopia_outcome["decision"]["attention_priority"], "low")
            self.assertEqual(report["providers"]["outlookmail"]["safety_review_count"], 1)
            self.assertEqual(
                report["providers"]["outlookmail"]["safety_reviews"][0]["message_id"],
                "o1",
            )
            utopia_call = next(payload for payload in llm_client.calls if payload["sender"] == "Utopia")
            self.assertEqual(utopia_call["memory_context"]["cluster_policy_key"], "outlookmail:utopia")

    def test_runtime_cascade_llm_limit_is_global_across_providers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proton_dir = root / "protonmail"
            outlook_dir = root / "outlookmail"
            self._write_batch(
                proton_dir,
                "founder-proton-batch-1",
                "founder-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": "Utopia",
                        "subject": "Age 1",
                        "snippet": "Update.",
                        "body": "Update.",
                    }
                ],
            )
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Another Sender",
                        "subject": "Another mystery",
                        "snippet": "Unknown.",
                        "body": "Unknown.",
                    }
                ],
            )
            llm_client = FakeRuntimeCascadeClient()

            report = build_runtime_cascade_report(
                [("protonmail", proton_dir), ("outlookmail", outlook_dir)],
                extra_rules=[],
                cluster_decision_pack={},
                llm_client=llm_client,
                llm_limit=1,
            )

            self.assertEqual(report["summary"]["llm_call_count"], 1)
            self.assertEqual(len(llm_client.calls), 1)

    def test_runtime_cascade_allocates_llm_calls_across_providers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proton_dir = root / "protonmail"
            outlook_dir = root / "outlookmail"
            self._write_batch(
                proton_dir,
                "founder-proton-batch-1",
                "founder-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": "Utopia",
                        "subject": "Age 1",
                        "snippet": "Update.",
                        "body": "Update.",
                    },
                    {
                        "message_id": "p2",
                        "sender": "Proton mystery",
                        "subject": "Unknown proton",
                        "snippet": "Unknown.",
                        "body": "Unknown.",
                    },
                ],
            )
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Hotmail mystery",
                        "subject": "Unknown hotmail",
                        "snippet": "Unknown.",
                        "body": "Unknown.",
                    },
                    {
                        "message_id": "o2",
                        "sender": "Another hotmail mystery",
                        "subject": "Another unknown hotmail",
                        "snippet": "Unknown.",
                        "body": "Unknown.",
                    },
                ],
            )
            llm_client = FakeRuntimeCascadeClient()

            report = build_runtime_cascade_report(
                [("protonmail", proton_dir), ("outlookmail", outlook_dir)],
                extra_rules=[],
                cluster_decision_pack={},
                llm_client=llm_client,
                llm_limit=2,
            )

            self.assertEqual(report["summary"]["llm_call_count"], 2)
            self.assertEqual(report["providers"]["protonmail"]["llm_call_count"], 1)
            self.assertEqual(report["providers"]["outlookmail"]["llm_call_count"], 1)

    def test_runtime_cascade_preserves_unresolved_provenance_when_llm_abstains(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proton_dir = root / "protonmail"
            self._write_batch(
                proton_dir,
                "founder-proton-batch-1",
                "founder-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": "Unknown Sender",
                        "subject": "Urgent invoice notice",
                        "snippet": "Unknown.",
                        "body": "Unknown.",
                    }
                ],
            )
            llm_client = FakeRuntimeCascadeClient()

            report = build_runtime_cascade_report(
                [("protonmail", proton_dir)],
                extra_rules=[],
                cluster_decision_pack={},
                llm_client=llm_client,
                llm_limit=1,
            )

            unresolved = report["providers"]["protonmail"]["outcomes"][0]
            self.assertEqual(unresolved["stage"], "unresolved")
            self.assertEqual(unresolved["decision_provenance"]["decision_source"], "unresolved")
            self.assertTrue(unresolved["decision_provenance"]["llm_used"])
            self.assertTrue(unresolved["decision_provenance"]["llm_abstained"])
            self.assertTrue(unresolved["decision"]["abstained"])
            self.assertEqual(unresolved["decision"]["actionability"], "review")
            self.assertEqual(unresolved["decision"]["risk_state"], "suspicious")
            self.assertEqual(unresolved["decision"]["safety_lane"], "suspicious")
            self.assertTrue(unresolved["decision"]["requires_caution"])
            self.assertEqual(report["summary"]["safety_counts"]["suspicious"], 1)
            self.assertEqual(report["providers"]["protonmail"]["safety_review_count"], 1)
            self.assertEqual(
                report["providers"]["protonmail"]["safety_reviews"][0]["message_id"],
                "p1",
            )

    def test_runtime_cascade_retrieves_approved_safety_disposition_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": '"Pest Solutions" <alerts@pestsolutions.test>',
                        "subject": "Service report 123456",
                        "snippet": "Open attached report.",
                        "body": "Open attached report.",
                    }
                ],
            )
            (gmail_dir / "safety_dispositions.json").write_text(
                json.dumps(
                    {
                        "status": "PROTOTYPE - local safety review dispositions",
                        "generated_at": "2026-06-28T00:00:00Z",
                        "disposition_count": 1,
                        "dispositions": [
                            {
                                "id": "safety-gmail-sender-phishing-alerts-pestsolutions-test",
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "source_batch_id": "founder-test-batch-0",
                                "source_message_ids": ["seed-1"],
                                "scope": "sender",
                                "disposition": "phishing",
                                "source_examples": [
                                    {
                                        "provider": "gmail",
                                        "message_id": "seed-1",
                                        "sender": '"Pest Solutions" <alerts@pestsolutions.test>',
                                        "subject": "Service report 999999",
                                        "date": "2026-06-27T00:00:00Z",
                                        "final_labels": [],
                                    }
                                ],
                                "explanation": "Unexpected fake service notices.",
                                "preview": {"match_count": 1, "matches": []},
                                "status": "approved",
                                "created_at": "2026-06-28T00:00:00Z",
                                "updated_at": "2026-06-28T00:00:00Z",
                                "review_notes": "Approved by founder.",
                            }
                        ],
                    },
                    indent=2,
                )
            )
            llm_client = FakeRuntimeCascadeClient()

            report = build_runtime_cascade_report(
                [("gmail", gmail_dir)],
                extra_rules=[],
                cluster_decision_pack={},
                llm_client=llm_client,
                llm_limit=1,
            )

            outcome = report["providers"]["gmail"]["outcomes"][0]
            self.assertEqual(outcome["decision"]["risk_state"], "suspicious")
            self.assertTrue(outcome["decision_provenance"]["safety_memory_used"])
            self.assertEqual(
                outcome["decision_provenance"]["retrieved_safety_keys"],
                ["safety-gmail-sender-phishing-alerts-pestsolutions-test"],
            )
            self.assertEqual(report["summary"]["safety_memory_hit_count"], 1)
            self.assertEqual(
                llm_client.calls[0]["memory_context"]["safety_context"]["disposition"],
                "phishing",
            )

    def test_runtime_cascade_keeps_phishing_family_in_suspicious_lane_after_memory_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": '"Order Confirmation" <alerts@fake-order.test>',
                        "subject": "ConfirmReceipt",
                        "snippet": "Claim your free gift card.",
                        "body": "Claim your free gift card.",
                    }
                ],
            )
            (gmail_dir / "safety_dispositions.json").write_text(
                json.dumps(
                    {
                        "status": "PROTOTYPE - local safety review dispositions",
                        "generated_at": "2026-06-28T00:00:00Z",
                        "disposition_count": 1,
                        "dispositions": [
                            {
                                "id": "safety-gmail-sender-phishing-alerts-fake-order-test",
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "source_batch_id": "seed-batch",
                                "source_message_ids": ["seed-1"],
                                "scope": "sender",
                                "disposition": "phishing",
                                "source_examples": [
                                    {
                                        "provider": "gmail",
                                        "message_id": "seed-1",
                                        "sender": '"Order Confirmation" <alerts@fake-order.test>',
                                        "subject": "ConfirmReceipt",
                                        "date": "2026-06-27T00:00:00Z",
                                        "final_labels": [],
                                    }
                                ],
                                "explanation": "Fake gift card claim scam.",
                                "preview": {"match_count": 1, "matches": []},
                                "status": "approved",
                                "created_at": "2026-06-28T00:00:00Z",
                                "updated_at": "2026-06-28T00:00:00Z",
                                "review_notes": "Approved by founder.",
                            }
                        ],
                    },
                    indent=2,
                )
            )
            rules = [
                TeachableRule(
                    id="shadow-gmail-002",
                    instruction="Anything from alerts@fake-order.test should be spam-low-value.",
                    label="spam-low-value",
                    terms=("alerts@fake-order.test",),
                    keep_visible=False,
                    created_at="2026-06-28T00:00:00Z",
                    providers=("gmail",),
                    enabled=True,
                    source_examples=(
                        {
                            "sender": '"Order Confirmation" <alerts@fake-order.test>',
                            "subject": "ConfirmReceipt",
                        },
                    ),
                    scope="sender",
                    match_mode="sender",
                )
            ]

            report = build_runtime_cascade_report(
                [("gmail", gmail_dir)],
                extra_rules=rules,
                cluster_decision_pack={},
                llm_client=FakeRuntimeCascadeClient(),
                llm_limit=1,
            )

            outcome = report["providers"]["gmail"]["outcomes"][0]
            self.assertIn(outcome["stage"], {"deterministic", "accepted-memory"})
            self.assertTrue(outcome["labels"])
            self.assertEqual(outcome["decision"]["risk_state"], "suspicious")
            self.assertEqual(outcome["decision"]["safety_lane"], "suspicious")
            self.assertTrue(outcome["decision"]["requires_caution"])
            self.assertTrue(outcome["decision_provenance"]["safety_memory_used"])
            self.assertEqual(
                outcome["decision_provenance"]["retrieved_safety_keys"],
                ["safety-gmail-sender-phishing-alerts-fake-order-test"],
            )
            self.assertEqual(report["summary"]["safety_memory_hit_count"], 1)
            self.assertEqual(report["summary"]["safety_counts"]["suspicious"], 1)

    def test_runtime_cascade_matches_family_cluster_safety_disposition_across_spoofed_senders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outlook_dir = root / "outlookmail"
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "CA.77",
                        "subject": "Order",
                        "snippet": "UPS You Tracking Order:#eJy-09973260 You have (1) message from us. CONFIRM NOW!",
                        "body": "UPS You Tracking Order:#eJy-09973260 You have (1) message from us. CONFIRM NOW!",
                    }
                ],
            )
            (outlook_dir / "safety_dispositions.json").write_text(
                json.dumps(
                    {
                        "status": "PROTOTYPE - local safety review dispositions",
                        "generated_at": "2026-06-28T00:00:00Z",
                        "disposition_count": 1,
                        "dispositions": [
                            {
                                "id": "safety-outlookmail-family-cluster-phishing-shipping-cluster",
                                "provider": "outlookmail",
                                "account_id": "founder-hotmail",
                                "source_batch_id": "seed-batch",
                                "source_message_ids": ["seed-1", "seed-2"],
                                "scope": "family-cluster",
                                "disposition": "phishing",
                                "source_examples": [
                                    {
                                        "provider": "outlookmail",
                                        "message_id": "seed-1",
                                        "sender": "UPS41538",
                                        "subject": "Package",
                                        "date": "2026-06-27T00:00:00Z",
                                        "snippet": "Package Delivery Notification Delivery on Hold Tracking ID# 1Z416074275839315 Confirm Address",
                                        "final_labels": [],
                                    },
                                    {
                                        "provider": "outlookmail",
                                        "message_id": "seed-2",
                                        "sender": "EXPDeIivery",
                                        "subject": "Fw: lD#es-09898",
                                        "date": "2026-06-27T00:00:00Z",
                                        "snippet": "Express Delivery Notice Package Delivery Suspended Tracking Number: #zm-2038425426 Confirm Address",
                                        "final_labels": [],
                                    },
                                ],
                                "explanation": "Spoofed package-delivery scams.",
                                "match_signals": {
                                    "sender_terms": ["ups41538", "expdelivery"],
                                    "subject_terms": ["package", "fw: ld#es-#####"],
                                    "content_terms": ["delivery", "package delivery", "tracking", "confirm", "confirm address"],
                                    "min_content_terms": 2,
                                },
                                "preview": {"match_count": 3, "matches": []},
                                "status": "approved",
                                "created_at": "2026-06-28T00:00:00Z",
                                "updated_at": "2026-06-28T00:00:00Z",
                                "review_notes": "Approved by founder.",
                            }
                        ],
                    },
                    indent=2,
                )
            )

            report = build_runtime_cascade_report(
                [("outlookmail", outlook_dir)],
                extra_rules=[],
                cluster_decision_pack={},
                llm_client=FakeRuntimeCascadeClient(),
                llm_limit=1,
            )

            outcome = report["providers"]["outlookmail"]["outcomes"][0]
            self.assertEqual(outcome["decision"]["risk_state"], "suspicious")
            self.assertTrue(outcome["decision_provenance"]["safety_memory_used"])
            self.assertEqual(
                outcome["decision_provenance"]["retrieved_safety_keys"],
                ["safety-outlookmail-family-cluster-phishing-shipping-cluster"],
            )
            self.assertEqual(report["summary"]["safety_memory_hit_count"], 1)

    def _write_batch(
        self,
        storage_dir: Path,
        batch_id: str,
        account_id: str,
        provider: str,
        items: list[dict],
    ) -> None:
        batches_dir = storage_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        (batches_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": account_id,
                    "provider": provider,
                    "items": items,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
