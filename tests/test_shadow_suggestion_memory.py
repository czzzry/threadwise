import json
import tempfile
import unittest
from pathlib import Path

from src.shadow_suggestion_memory import (
    OpenAIShadowFamilySuggestionClient,
    ShadowSuggestionCandidate,
    ShadowSuggestionMemory,
    build_shadow_suggestion_candidates,
)


class ShadowSuggestionMemoryTests(unittest.TestCase):
    def test_build_shadow_suggestion_candidates_proposes_labels_for_discovery_families(self) -> None:
        report = {
            "providers": {
                "outlookmail": {
                    "top_unlabeled_families_by_split": {
                        "discovery": [
                            {
                                "sender_key": "microsoft@example.com",
                                "subject_key": "security alert for your linked google account",
                                "count": 3,
                                "examples": [
                                    {
                                        "sender": "Google <no-reply@accounts.google.com>",
                                        "subject": "Security alert for your linked Google Account",
                                    }
                                ],
                            }
                        ]
                    }
                }
            }
        }

        candidates = build_shadow_suggestion_candidates(report, limit_per_provider=5)

        self.assertEqual(candidates["outlookmail"][0]["suggested_labels"], ["account-security"])
        self.assertEqual(candidates["outlookmail"][0]["status"], "pending")
        self.assertIn("security", candidates["outlookmail"][0]["rationale"].lower())

    def test_merge_candidates_preserves_existing_review_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = ShadowSuggestionMemory(Path(temp_dir) / "shadow_suggestion_memory.json")
            first = ShadowSuggestionCandidate(
                provider="outlookmail",
                sender_key="google@example.com",
                subject_key="security alert",
                split="discovery",
                count=2,
                suggested_labels=("account-security",),
                rationale="Looks security-related.",
                evidence_terms=("security alert",),
                source_examples=({"subject": "Security alert"},),
                generated_by="heuristic-shadow-family-suggester",
                confidence="high",
            )
            saved = memory.merge_candidates([first])[0]
            payload = json.loads(memory.path.read_text())
            payload["candidates"][0]["status"] = "accepted"
            payload["candidates"][0]["accepted_labels"] = ["account-security"]
            memory.path.write_text(json.dumps(payload, indent=2))

            second = ShadowSuggestionCandidate(
                provider="outlookmail",
                sender_key="google@example.com",
                subject_key="security alert",
                split="discovery",
                count=5,
                suggested_labels=("account-security",),
                rationale="Looks security-related.",
                evidence_terms=("security alert", "linked google account"),
                source_examples=({"subject": "Security alert"},),
                generated_by="heuristic-shadow-family-suggester",
                confidence="high",
            )
            merged = memory.merge_candidates([second])[0]

            self.assertEqual(saved.status, "pending")
            self.assertEqual(merged.status, "accepted")
            self.assertEqual(merged.accepted_labels, ("account-security",))
            self.assertEqual(merged.count, 5)
            self.assertEqual(json.loads(memory.path.read_text())["candidate_count"], 1)

    def test_merge_candidates_keeps_reviewed_candidates_not_present_in_latest_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = ShadowSuggestionMemory(Path(temp_dir) / "shadow_suggestion_memory.json")
            memory.merge_candidates(
                [
                    ShadowSuggestionCandidate(
                        provider="outlookmail",
                        sender_key="sony",
                        subject_key="change your password",
                        split="discovery",
                        count=2,
                        suggested_labels=("account-security",),
                        rationale="Password flow.",
                        evidence_terms=("password",),
                        source_examples=({"subject": "Change your Password"},),
                        generated_by="openai-shadow-family-suggester",
                        confidence="high",
                    )
                ]
            )
            memory.review_candidate(
                "outlookmail",
                "sony",
                "change your password",
                "accepted",
                accepted_labels=["account-security"],
            )

            merged = memory.merge_candidates([])

            self.assertEqual(len(merged), 1)
            self.assertEqual(merged[0].status, "accepted")

    def test_build_shadow_suggestion_candidates_prefers_model_when_available(self) -> None:
        class FakeModelClient:
            def suggest_for_family(self, provider: str, family: dict) -> dict:
                return {
                    "labels": ["reply-needed"],
                    "rationale": "Model says this likely needs attention.",
                    "evidence_terms": ["action required"],
                    "confidence": "high",
                }

        report = {
            "providers": {
                "protonmail": {
                    "top_unlabeled_families_by_split": {
                        "discovery": [
                            {
                                "sender_key": "workatastartup@ycombinator.com",
                                "subject_key": "still looking for a job? (action required)",
                                "count": 2,
                                "examples": [
                                    {
                                        "sender": "Work at a Startup <workatastartup@ycombinator.com>",
                                        "subject": "Still looking for a job? (action required)",
                                    }
                                ],
                            }
                        ]
                    }
                }
            }
        }

        candidates = build_shadow_suggestion_candidates(
            report,
            limit_per_provider=5,
            model_client=FakeModelClient(),
        )

        self.assertEqual(candidates["protonmail"][0]["suggested_labels"], ["reply-needed"])
        self.assertEqual(candidates["protonmail"][0]["generated_by"], "openai-shadow-family-suggester")

    def test_review_candidate_and_export_accepted_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "shadow_suggestion_memory.json"
            rules_path = Path(temp_dir) / "accepted_shadow_teachable_rules.json"
            memory = ShadowSuggestionMemory(memory_path)
            memory.merge_candidates(
                [
                    ShadowSuggestionCandidate(
                        provider="outlookmail",
                        sender_key="sony",
                        subject_key="change your password",
                        split="discovery",
                        count=2,
                        suggested_labels=("account-security",),
                        rationale="Password flow.",
                        evidence_terms=("password",),
                        source_examples=({"subject": "Change your Password"},),
                        generated_by="openai-shadow-family-suggester",
                        confidence="high",
                    )
                ]
            )

            reviewed = memory.review_candidate(
                "outlookmail",
                "sony",
                "change your password",
                "accepted",
                accepted_labels=["account-security"],
                review_notes="Good match.",
            )
            exported = memory.export_accepted_rules(rules_path)
            payload = json.loads(rules_path.read_text())

            self.assertEqual(reviewed.status, "accepted")
            self.assertEqual(reviewed.accepted_labels, ("account-security",))
            self.assertEqual(len(exported), 1)
            self.assertEqual(exported[0].label, "account-security")
            self.assertIn("sony", exported[0].terms)
            self.assertEqual(exported[0].providers, ("outlookmail",))
            self.assertEqual(payload["rules"][0]["label"], "account-security")
            self.assertEqual(payload["provider_scope"], "per-rule")
            self.assertEqual(payload["exported_candidate_keys"][0]["provider"], "outlookmail")
            self.assertEqual(payload["exported_rule_count"], 1)
            self.assertTrue(payload["rules"][0]["id"].startswith("shadow-outlookmail-"))

    def test_export_accepted_rules_keeps_multiple_labels_including_low_value_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "shadow_suggestion_memory.json"
            rules_path = Path(temp_dir) / "accepted_shadow_teachable_rules.json"
            memory = ShadowSuggestionMemory(memory_path)
            memory.merge_candidates(
                [
                    ShadowSuggestionCandidate(
                        provider="outlookmail",
                        sender_key="lieferando",
                        subject_key="dein gutschein",
                        split="discovery",
                        count=5,
                        suggested_labels=("promotions", "spam-low-value"),
                        rationale="Promo mail.",
                        evidence_terms=("gutschein",),
                        source_examples=({"subject": "Dein Gutschein"},),
                        generated_by="openai-shadow-family-suggester",
                        confidence="high",
                    )
                ]
            )

            memory.review_candidate(
                "outlookmail",
                "lieferando",
                "dein gutschein",
                "accepted",
                accepted_labels=["promotions", "spam-low-value"],
            )
            exported = memory.export_accepted_rules(rules_path)
            payload = json.loads(rules_path.read_text())

            self.assertEqual(len(exported), 2)
            self.assertEqual([rule.label for rule in exported], ["promotions", "spam-low-value"])
            self.assertEqual(payload["exported_rule_count"], 2)
            self.assertEqual([rule["label"] for rule in payload["rules"]], ["promotions", "spam-low-value"])
            self.assertNotEqual(payload["rules"][0]["id"], payload["rules"][1]["id"])

    def test_export_accepted_rules_preserves_non_shadow_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "shadow_suggestion_memory.json"
            rules_path = Path(temp_dir) / "accepted_shadow_teachable_rules.json"
            rules_path.write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "id": "teach-999",
                                "instruction": "Anything from ebay@reply.ebay.de should be promotions.",
                                "label": "promotions",
                                "terms": ["ebay@reply.ebay.de"],
                                "keep_visible": False,
                                "created_at": "2026-06-29T00:00:00Z",
                                "providers": ["gmail"],
                                "enabled": True,
                                "source_examples": [],
                                "scope": "sender",
                                "match_mode": "sender",
                                "provenance": {"source": "human-correction-proposal"},
                                "updated_at": "2026-06-29T00:00:00Z",
                            }
                        ]
                    },
                    indent=2,
                )
            )
            memory = ShadowSuggestionMemory(memory_path)
            memory.merge_candidates(
                [
                    ShadowSuggestionCandidate(
                        provider="outlookmail",
                        sender_key="sony",
                        subject_key="change your password",
                        split="discovery",
                        count=2,
                        suggested_labels=("account-security",),
                        rationale="Password flow.",
                        evidence_terms=("password",),
                        source_examples=({"subject": "Change your Password"},),
                        generated_by="openai-shadow-family-suggester",
                        confidence="high",
                    )
                ]
            )
            memory.review_candidate(
                "outlookmail",
                "sony",
                "change your password",
                "accepted",
                accepted_labels=["account-security"],
            )

            memory.export_accepted_rules(rules_path)
            payload = json.loads(rules_path.read_text())

            self.assertEqual(len(payload["rules"]), 2)
            self.assertTrue(any(rule["id"] == "teach-999" for rule in payload["rules"]))
            self.assertTrue(any(rule["id"].startswith("shadow-outlookmail-") for rule in payload["rules"]))

    def test_rejected_candidate_clears_accepted_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = ShadowSuggestionMemory(Path(temp_dir) / "shadow_suggestion_memory.json")
            memory.merge_candidates(
                [
                    ShadowSuggestionCandidate(
                        provider="outlookmail",
                        sender_key="sony",
                        subject_key="change your password",
                        split="discovery",
                        count=2,
                        suggested_labels=("account-security",),
                        rationale="Password flow.",
                        evidence_terms=("password",),
                        source_examples=({"subject": "Change your Password"},),
                        generated_by="openai-shadow-family-suggester",
                        confidence="high",
                    )
                ]
            )
            memory.review_candidate(
                "outlookmail",
                "sony",
                "change your password",
                "accepted",
                accepted_labels=["account-security"],
            )

            rejected = memory.review_candidate(
                "outlookmail",
                "sony",
                "change your password",
                "rejected",
                review_notes="Not useful.",
            )

            self.assertEqual(rejected.status, "rejected")
            self.assertEqual(rejected.accepted_labels, ())

    def test_review_candidate_rejects_unknown_accepted_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = ShadowSuggestionMemory(Path(temp_dir) / "shadow_suggestion_memory.json")
            memory.merge_candidates(
                [
                    ShadowSuggestionCandidate(
                        provider="protonmail",
                        sender_key="confirm@eightfold.ai",
                        subject_key="verify your email",
                        split="discovery",
                        count=1,
                        suggested_labels=("account-security",),
                        rationale="Verification flow.",
                        evidence_terms=("verify your email",),
                        source_examples=({"subject": "Verify your email"},),
                        generated_by="openai-shadow-family-suggester",
                        confidence="high",
                    )
                ]
            )

            with self.assertRaises(ValueError):
                memory.review_candidate(
                    "protonmail",
                    "confirm@eightfold.ai",
                    "verify your email",
                    "accepted",
                    accepted_labels=["not-a-real-label"],
                )

    def test_list_candidates_deduplicates_by_candidate_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shadow_suggestion_memory.json"
            path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "sony",
                                "subject_key": "change your password",
                                "split": "discovery",
                                "count": 1,
                                "suggested_labels": ["account-security"],
                                "rationale": "Old",
                                "evidence_terms": ["password"],
                                "source_examples": [],
                                "generated_by": "heuristic-shadow-family-suggester",
                                "confidence": "low",
                                "status": "pending",
                            },
                            {
                                "provider": "outlookmail",
                                "sender_key": "sony",
                                "subject_key": "change your password",
                                "split": "discovery",
                                "count": 4,
                                "suggested_labels": ["account-security"],
                                "rationale": "New",
                                "evidence_terms": ["password"],
                                "source_examples": [],
                                "generated_by": "openai-shadow-family-suggester",
                                "confidence": "high",
                                "status": "accepted",
                                "accepted_labels": ["account-security"],
                            },
                        ]
                    },
                    indent=2,
                )
            )

            listed = ShadowSuggestionMemory(path).list_candidates()

            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0].count, 4)
            self.assertEqual(listed[0].status, "accepted")


if __name__ == "__main__":
    unittest.main()
