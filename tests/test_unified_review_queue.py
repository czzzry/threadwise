import json
import tempfile
import unittest
from pathlib import Path

from src.local_artifacts import (
    accepted_shadow_rules_path,
    founder_answer_pack_path,
    memory_proposals_path,
    safety_dispositions_path,
    shadow_suggestion_memory_path,
)
from src.memory_proposal_store import MemoryProposalStore, build_memory_proposal
from src.safety_disposition_store import SafetyDispositionStore, build_safety_disposition
from src.shadow_suggestion_memory import ShadowSuggestionCandidate, ShadowSuggestionMemory
from src.unified_review_queue import UnifiedReviewQueue


class UnifiedReviewQueueTests(unittest.TestCase):
    def test_build_queue_collects_memory_shadow_safety_runtime_and_founder_question_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir, provider_dirs = self._bootstrap_dirs(root)
            outlook_dir = provider_dirs["outlookmail"]
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Vendor <vendor@example.com>",
                        "subject": "30 % Rabatt",
                        "snippet": "Deal.",
                        "body": "Deal.",
                        "final_labels": ["promotions"],
                    }
                ],
            )
            storage_items = [
                {
                    "provider": "outlookmail",
                    "account_id": "founder-hotmail",
                    "batch_id": "founder-hotmail-batch-1",
                    "message_id": "o1",
                    "sender": "Vendor <vendor@example.com>",
                    "subject": "30 % Rabatt",
                    "date": "2026-06-28T00:00:00Z",
                    "final_labels": ["promotions"],
                }
            ]
            proposal_store = MemoryProposalStore(memory_proposals_path(output_dir))
            proposal_store.save_proposal(
                build_memory_proposal(
                    provider="outlookmail",
                    account_id="founder-hotmail",
                    source_batch_id="founder-hotmail-batch-1",
                    selected_items=storage_items,
                    scope="sender-cluster",
                    label="promotions",
                    explanation="Promo family.",
                    storage_items=storage_items,
                )
            )
            safety_store = SafetyDispositionStore(safety_dispositions_path(outlook_dir))
            safety_store.save_disposition(
                build_safety_disposition(
                    provider="outlookmail",
                    account_id="founder-hotmail",
                    source_batch_id="founder-hotmail-batch-1",
                    selected_items=storage_items,
                    scope="sender-cluster",
                    disposition="phishing",
                    explanation="Scam pattern.",
                    storage_items=storage_items,
                )
            )
            shadow_memory = ShadowSuggestionMemory(shadow_suggestion_memory_path(output_dir))
            shadow_memory.merge_candidates(
                [
                    ShadowSuggestionCandidate(
                        provider="outlookmail",
                        sender_key="vendor@example.com",
                        subject_key="30 % rabatt",
                        split="discovery",
                        count=4,
                        suggested_labels=("promotions",),
                        rationale="Promo family.",
                        evidence_terms=("rabatt",),
                        source_examples=({"sender": "Vendor", "subject": "30 % Rabatt"},),
                        generated_by="openai-shadow-family-suggester",
                        confidence="high",
                    )
                ]
            )
            founder_pack = {
                "generated_at": "2026-06-29T00:00:00Z",
                "pack_path": str(founder_answer_pack_path(output_dir, "founder-answer-pack-1")),
                "questions": [
                    {
                        "question_id": "question-marketing-preference",
                        "theme": "marketing-preference",
                        "title": "How should recurring marketing mail be handled?",
                        "prompt": "Prompt.",
                        "providers": ["outlookmail"],
                        "family_count": 1,
                        "estimated_unblocked_messages": 3,
                        "answer_options": [
                            {
                                "answer_key": "low_value_default",
                                "description": "Default these families to promo/low-value handling.",
                                "proposal_drafts": [
                                    {
                                        "id": "proposal-outlookmail-sender-cluster-promotions-vendor-rabatt",
                                        "provider": "outlookmail",
                                        "account_id": "founder-hotmail",
                                        "source_batch_id": "founder-hotmail-batch-1",
                                        "source_message_ids": ["o1"],
                                        "scope": "sender-cluster",
                                        "label": "promotions",
                                        "instruction": "Anything from vendor should be promotions.",
                                        "terms": ["vendor"],
                                        "source_examples": storage_items,
                                        "explanation": "Draft.",
                                        "preview": {"match_count": 1, "matches": []},
                                        "status": "pending",
                                        "created_at": "2026-06-28T00:00:00Z",
                                        "updated_at": "2026-06-28T00:00:00Z",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
            runtime_report = {
                "generated_at": "2026-06-29T00:00:00Z",
                "report_path": str(output_dir / "runtime_cascades" / "runtime-cascade-1.json"),
                "providers": {
                    "outlookmail": {
                        "outcomes": [
                            {
                                "provider": "outlookmail",
                                "account_id": "founder-hotmail",
                                "batch_id": "founder-hotmail-batch-1",
                                "message_id": "o1",
                                "sender": "Vendor <vendor@example.com>",
                                "subject": "30 % Rabatt",
                                "sender_key": "vendor@example.com",
                                "subject_key": "30 % rabatt",
                                "stage": "llm-escalation",
                                "labels": ["promotions"],
                                "llm_rationale": "Promo family.",
                                "llm_confidence": "high",
                                "decision_provenance": {"llm_model": "gpt-test"},
                                "decision": {"confidence": "high", "safety_lane": "ordinary"},
                            }
                        ]
                    }
                },
            }

            queue = UnifiedReviewQueue(output_dir, list(provider_dirs.items()))
            payload = queue.build_queue(runtime_report=runtime_report, founder_answer_pack=founder_pack)

            self.assertEqual(payload["summary"]["item_count"], 5)
            self.assertEqual(payload["summary"]["pending_by_type"]["runtime-llm-candidate"], 1)
            self.assertEqual(payload["summary"]["pending_by_type"]["founder-question"], 1)
            item_types = {item["item_type"] for item in payload["items"]}
            self.assertEqual(
                item_types,
                {
                    "memory-proposal",
                    "shadow-suggestion",
                    "safety-disposition",
                    "runtime-llm-candidate",
                    "founder-question",
                },
            )

    def test_approving_runtime_llm_candidate_promotes_rules_into_durable_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir, provider_dirs = self._bootstrap_dirs(root)
            outlook_dir = provider_dirs["outlookmail"]
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Vendor <vendor@example.com>",
                        "subject": "30 % Rabatt",
                        "snippet": "Deal.",
                        "body": "Deal.",
                    }
                ],
            )
            runtime_report = {
                "generated_at": "2026-06-29T00:00:00Z",
                "report_path": str(output_dir / "runtime_cascades" / "runtime-cascade-1.json"),
                "providers": {
                    "outlookmail": {
                        "outcomes": [
                            {
                                "provider": "outlookmail",
                                "account_id": "founder-hotmail",
                                "batch_id": "founder-hotmail-batch-1",
                                "message_id": "o1",
                                "sender": "Vendor <vendor@example.com>",
                                "subject": "30 % Rabatt",
                                "sender_key": "vendor@example.com",
                                "subject_key": "30 % rabatt",
                                "stage": "llm-escalation",
                                "labels": ["promotions"],
                                "llm_rationale": "Promo family.",
                                "llm_confidence": "high",
                                "decision_provenance": {"llm_model": "gpt-test"},
                                "decision": {"confidence": "high", "safety_lane": "ordinary"},
                            }
                        ]
                    }
                },
            }

            queue = UnifiedReviewQueue(output_dir, list(provider_dirs.items()))
            built = queue.build_queue(runtime_report=runtime_report)
            item = next(candidate for candidate in built["items"] if candidate["item_type"] == "runtime-llm-candidate")

            result = queue.review_item(item["item_id"], action="approve", notes="Looks right.")

            rules_payload = json.loads(accepted_shadow_rules_path(output_dir).read_text())
            self.assertEqual(result["status"], "approved")
            self.assertEqual(len(result["approved_rule_ids"]), 1)
            self.assertEqual(len(rules_payload["rules"]), 1)
            self.assertEqual(rules_payload["rules"][0]["providers"], ["outlookmail"])

    def test_answering_founder_question_applies_proposals_and_writes_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir, provider_dirs = self._bootstrap_dirs(root)
            outlook_dir = provider_dirs["outlookmail"]
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Vendor <vendor@example.com>",
                        "subject": "30 % Rabatt",
                        "snippet": "Deal.",
                        "body": "Deal.",
                    }
                ],
            )
            review_pack = {
                "generated_at": "2026-06-29T00:00:00Z",
                "pack_path": str(founder_answer_pack_path(output_dir, "founder-answer-pack-1")),
                "questions": [
                    {
                        "question_id": "question-marketing-preference",
                        "theme": "marketing-preference",
                        "title": "How should recurring marketing mail be handled?",
                        "prompt": "Prompt.",
                        "providers": ["outlookmail"],
                        "family_count": 1,
                        "estimated_unblocked_messages": 1,
                        "answer_options": [
                            {
                                "answer_key": "low_value_default",
                                "description": "Default these families to promo/low-value handling.",
                                "proposal_drafts": [
                                    {
                                        "id": "proposal-outlookmail-sender-cluster-promotions-vendor-rabatt",
                                        "provider": "outlookmail",
                                        "account_id": "founder-hotmail",
                                        "source_batch_id": "founder-hotmail-batch-1",
                                        "source_message_ids": ["o1"],
                                        "scope": "sender-cluster",
                                        "label": "promotions",
                                        "instruction": "Anything from vendor should be promotions.",
                                        "terms": ["vendor"],
                                        "source_examples": [
                                            {
                                                "message_id": "o1",
                                                "sender": "Vendor <vendor@example.com>",
                                                "subject": "30 % Rabatt",
                                            }
                                        ],
                                        "explanation": "Draft.",
                                        "preview": {"match_count": 1, "matches": []},
                                        "status": "pending",
                                        "created_at": "2026-06-28T00:00:00Z",
                                        "updated_at": "2026-06-28T00:00:00Z",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
            queue = UnifiedReviewQueue(output_dir, list(provider_dirs.items()))
            built = queue.build_queue(founder_answer_pack=review_pack)
            item = next(candidate for candidate in built["items"] if candidate["item_type"] == "founder-question")

            result = queue.review_item(
                item["item_id"],
                action="answer",
                answer_key="low_value_default",
                notes="Founder approved.",
            )

            rules_payload = json.loads(accepted_shadow_rules_path(output_dir).read_text())
            self.assertEqual(result["status"], "applied")
            self.assertEqual(len(rules_payload["rules"]), 1)
            self.assertEqual(rules_payload["rules"][0]["label"], "promotions")

    def test_queue_ranks_founder_question_ahead_of_runtime_candidate_when_payoff_is_higher(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir, provider_dirs = self._bootstrap_dirs(root)
            runtime_dir = output_dir / "runtime_cascades"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "founder_answer_packs").mkdir(parents=True, exist_ok=True)
            (output_dir / "latest_safety_triage_pass.json").write_text(
                json.dumps(
                    {
                        "provider_drivers": [{"provider": "outlookmail", "driver_score": 5}],
                        "next_review_payoffs": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "vendor@example.com",
                                "subject_key": "30 % rabatt",
                                "expected_resolved_messages": 4,
                            }
                        ],
                    },
                    indent=2,
                )
            )
            founder_pack = {
                "generated_at": "2026-06-29T00:00:00Z",
                "questions": [
                    {
                        "question_id": "question-marketing-preference",
                        "theme": "marketing-preference",
                        "title": "How should recurring marketing mail be handled?",
                        "prompt": "Prompt.",
                        "providers": ["outlookmail"],
                        "family_count": 2,
                        "estimated_unblocked_messages": 40,
                        "answer_options": [],
                    }
                ],
            }
            (output_dir / "founder_answer_packs" / "founder-answer-pack-1.json").write_text(json.dumps(founder_pack, indent=2))
            runtime_report = {
                "generated_at": "2026-06-29T00:00:00Z",
                "providers": {
                    "outlookmail": {
                        "outcomes": [
                            {
                                "provider": "outlookmail",
                                "account_id": "founder-hotmail",
                                "batch_id": "batch-1",
                                "message_id": "m-1",
                                "sender": "Vendor <vendor@example.com>",
                                "subject": "30 % Rabatt",
                                "sender_key": "vendor@example.com",
                                "subject_key": "30 % rabatt",
                                "stage": "llm-escalation",
                                "labels": ["promotions"],
                                "llm_rationale": "Promo family.",
                                "llm_confidence": "high",
                                "decision_provenance": {"llm_model": "gpt-test"},
                                "decision": {"confidence": "high", "safety_lane": "ordinary"},
                            }
                        ]
                    }
                },
            }
            (runtime_dir / "runtime-cascade-1.json").write_text(json.dumps(runtime_report, indent=2))

            queue = UnifiedReviewQueue(output_dir, list(provider_dirs.items()))
            payload = queue.build_queue()

            self.assertEqual(payload["items"][0]["item_type"], "founder-question")
            self.assertGreater(payload["items"][0]["rank"]["score"], payload["items"][1]["rank"]["score"])

    def test_build_queue_adds_hotspot_founder_questions_from_unresolved_gap_when_no_pack_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir, provider_dirs = self._bootstrap_dirs(root)
            gmail_dir = provider_dirs["gmail"]
            self._write_batch(
                gmail_dir,
                "gmail-batch-1",
                "founder-gmail",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": "Blinkist <hello@mail.blinkist.com>",
                        "subject": "A fresh idea for your weekend",
                        "snippet": "Read this next.",
                        "body": "Read this next.",
                    }
                ],
            )
            runtime_report = {
                "generated_at": "2026-06-29T00:00:00Z",
                "report_path": str(output_dir / "runtime_cascades" / "runtime-cascade-1.json"),
                "summary": {"message_count": 10, "unresolved_count": 4},
                "providers": {
                    "gmail": {
                        "unresolved_count": 4,
                        "outcomes": [
                            {
                                "provider": "gmail",
                                "account_id": "founder-gmail",
                                "batch_id": "gmail-batch-1",
                                "message_id": "g1",
                                "sender": "Blinkist <hello@mail.blinkist.com>",
                                "subject": "A fresh idea for your weekend",
                                "sender_key": "hello@mail.blinkist.com",
                                "subject_key": "a fresh idea for your weekend",
                                "stage": "unresolved",
                            }
                        ]
                        * 4,
                    }
                },
            }

            queue = UnifiedReviewQueue(output_dir, list(provider_dirs.items()))
            payload = queue.build_queue(runtime_report=runtime_report)

            hotspot_questions = [
                item
                for item in payload["items"]
                if item["item_type"] == "founder-question" and item["source_ref"].get("source") == "unresolved-gap"
            ]
            self.assertEqual(len(hotspot_questions), 1)
            question = hotspot_questions[0]
            self.assertEqual(question["provider"], "gmail")
            self.assertIn("hello@mail.blinkist.com", question["title"])
            self.assertEqual(question["summary"]["estimated_unblocked_messages"], 4)
            self.assertEqual(question["decision_payload"]["question"]["answer_options"][0]["answer_key"], "low_value_default")

    def test_answering_hotspot_founder_question_approves_memory_for_recurring_family(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir, provider_dirs = self._bootstrap_dirs(root)
            gmail_dir = provider_dirs["gmail"]
            self._write_batch(
                gmail_dir,
                "gmail-batch-1",
                "founder-gmail",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": "Blinkist <hello@mail.blinkist.com>",
                        "subject": "A fresh idea for your weekend",
                        "snippet": "Read this next.",
                        "body": "Read this next.",
                    }
                ],
            )
            runtime_report = {
                "generated_at": "2026-06-29T00:00:00Z",
                "report_path": str(output_dir / "runtime_cascades" / "runtime-cascade-1.json"),
                "summary": {"message_count": 10, "unresolved_count": 4},
                "providers": {
                    "gmail": {
                        "unresolved_count": 4,
                        "outcomes": [
                            {
                                "provider": "gmail",
                                "account_id": "founder-gmail",
                                "batch_id": "gmail-batch-1",
                                "message_id": "g1",
                                "sender": "Blinkist <hello@mail.blinkist.com>",
                                "subject": "A fresh idea for your weekend",
                                "sender_key": "hello@mail.blinkist.com",
                                "subject_key": "a fresh idea for your weekend",
                                "stage": "unresolved",
                            }
                        ]
                        * 4,
                    }
                },
            }

            queue = UnifiedReviewQueue(output_dir, list(provider_dirs.items()))
            built = queue.build_queue(runtime_report=runtime_report)
            question = next(
                item
                for item in built["items"]
                if item["item_type"] == "founder-question" and item["source_ref"].get("source") == "unresolved-gap"
            )

            result = queue.review_item(
                question["item_id"],
                action="answer",
                answer_key="low_value_default",
                notes="Looks like newsletter/promo.",
            )

            rules_payload = json.loads(accepted_shadow_rules_path(output_dir).read_text())
            self.assertEqual(result["status"], "applied")
            self.assertEqual(len(result["approved_rule_ids"]), 1)
            self.assertEqual(rules_payload["rules"][0]["providers"], ["gmail"])
            self.assertEqual(queue.load_queue()["summary"]["pending_count"], 0)

    def test_linkedin_direct_message_hotspot_uses_direct_message_answers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir, provider_dirs = self._bootstrap_dirs(root)
            gmail_dir = provider_dirs["gmail"]
            self._write_batch(
                gmail_dir,
                "gmail-batch-1",
                "founder-gmail",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": "Sophie Friend via LinkedIn <messaging-digest-noreply@linkedin.com>",
                        "subject": "Sophie just messaged you",
                        "snippet": "LinkedIn message",
                        "body": "LinkedIn message",
                    }
                ],
            )
            runtime_report = {
                "generated_at": "2026-06-29T00:00:00Z",
                "report_path": str(output_dir / "runtime_cascades" / "runtime-cascade-1.json"),
                "summary": {"message_count": 10, "unresolved_count": 7},
                "providers": {
                    "gmail": {
                        "unresolved_count": 7,
                        "outcomes": [
                            {
                                "provider": "gmail",
                                "account_id": "founder-gmail",
                                "batch_id": "gmail-batch-1",
                                "message_id": "g1",
                                "sender": "Sophie Friend via LinkedIn <messaging-digest-noreply@linkedin.com>",
                                "subject": "Sophie just messaged you",
                                "sender_key": "messaging-digest-noreply@linkedin.com",
                                "subject_key": "sophie just messaged you",
                                "stage": "unresolved",
                            }
                        ]
                        * 7,
                    }
                },
            }

            queue = UnifiedReviewQueue(output_dir, list(provider_dirs.items()))
            payload = queue.build_queue(runtime_report=runtime_report)
            question = next(
                item
                for item in payload["items"]
                if item["item_type"] == "founder-question"
                and item["source_ref"].get("source") == "unresolved-gap"
            )
            self.assertEqual(question["summary"]["theme"], "direct-message-handling")
            self.assertEqual(
                [option["answer_key"] for option in question["decision_payload"]["question"]["answer_options"]],
                ["personal_default", "sender_allowlist_only"],
            )

    def test_task_update_hotspot_uses_personal_vs_low_value_answers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir, provider_dirs = self._bootstrap_dirs(root)
            proton_dir = provider_dirs["protonmail"]
            self._write_batch(
                proton_dir,
                "proton-batch-1",
                "founder-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": '"ChatGPT" <noreply@tm.openai.com>',
                        "subject": "[Task Update] Augustine reading Book I.1–I.5 tonight",
                        "snippet": "Task update",
                        "body": "Task update",
                    }
                ],
            )
            runtime_report = {
                "generated_at": "2026-06-29T00:00:00Z",
                "report_path": str(output_dir / "runtime_cascades" / "runtime-cascade-1.json"),
                "summary": {"message_count": 10, "unresolved_count": 6},
                "providers": {
                    "protonmail": {
                        "unresolved_count": 6,
                        "outcomes": [
                            {
                                "provider": "protonmail",
                                "account_id": "founder-proton",
                                "batch_id": "proton-batch-1",
                                "message_id": "p1",
                                "sender": '"ChatGPT" <noreply@tm.openai.com>',
                                "subject": "[Task Update] Augustine reading Book I.1–I.5 tonight",
                                "sender_key": "noreply@tm.openai.com",
                                "subject_key": "[task update] augustine reading book i.#–i.# tonight",
                                "stage": "unresolved",
                            }
                        ]
                        * 6,
                    }
                },
            }

            queue = UnifiedReviewQueue(output_dir, list(provider_dirs.items()))
            payload = queue.build_queue(runtime_report=runtime_report)
            question = next(
                item
                for item in payload["items"]
                if item["item_type"] == "founder-question"
                and item["source_ref"].get("source") == "unresolved-gap"
            )
            self.assertEqual(question["summary"]["theme"], "personal-vs-low-value")
            self.assertEqual(
                [option["answer_key"] for option in question["decision_payload"]["question"]["answer_options"]],
                ["personal_default", "low_value_default"],
            )

    def _bootstrap_dirs(self, root: Path) -> tuple[Path, dict[str, Path]]:
        output_dir = root / "classifier_eval"
        provider_dirs = {
            "gmail": root / "gmail_fetch",
            "protonmail": root / "protonmail_fetch",
            "outlookmail": root / "outlookmail_fetch",
        }
        for path in provider_dirs.values():
            (path / "batches").mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir, provider_dirs

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
