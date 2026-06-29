import json
import tempfile
import unittest
from pathlib import Path

from src.local_artifacts import memory_proposals_path
from src.memory_proposal_store import MemoryProposalStore, build_memory_proposal, load_storage_items
from src.teachable_rule_memory import TeachableRuleMemory


class MemoryProposalStoreTests(unittest.TestCase):
    def test_build_sender_cluster_memory_proposal_and_approve_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage_dir = root / "gmail_fetch"
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": '"OpenAI" <noreply@tm.openai.com>',
                        "subject": "[Task Update] Weekly reflection",
                        "snippet": "Update.",
                        "body": "Update.",
                        "applied_labels": [],
                        "final_labels": ["newsletter"],
                    },
                    {
                        "message_id": "g2",
                        "sender": '"OpenAI" <noreply@tm.openai.com>',
                        "subject": "[Task Update] Daily notes",
                        "snippet": "Update.",
                        "body": "Update.",
                        "applied_labels": [],
                    },
                ],
            )
            items = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())["items"]
            storage_items = load_storage_items(storage_dir, "gmail")

            proposal = build_memory_proposal(
                provider="gmail",
                account_id="founder-test",
                source_batch_id="founder-test-batch-1",
                selected_items=[items[0]],
                scope="sender-cluster",
                label="newsletter",
                explanation="These task updates are low-priority reading.",
                storage_items=storage_items,
            )
            store = MemoryProposalStore(memory_proposals_path(storage_dir))
            store.save_proposal(proposal)
            rules_memory = TeachableRuleMemory(storage_dir / "teachable_classification_rules.json")

            approved = store.review_proposal(proposal.id, "approved", rules_memory=rules_memory, review_notes="Looks right.")

            self.assertEqual(approved.status, "approved")
            rules = rules_memory.list_rules()
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0].scope, "sender-cluster")
            self.assertEqual(rules[0].match_mode, "sender-cluster")
            self.assertEqual(rules[0].provenance["proposal_id"], proposal.id)

    def test_reject_proposal_does_not_write_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage_dir = root / "gmail_fetch"
            store = MemoryProposalStore(memory_proposals_path(storage_dir))
            proposal = build_memory_proposal(
                provider="gmail",
                account_id="founder-test",
                source_batch_id="founder-test-batch-1",
                selected_items=[
                    {
                        "message_id": "g1",
                        "sender": '"Vendor" <vendor@example.com>',
                        "subject": "Quarterly vendor update",
                        "date": "2026-06-28T00:00:00Z",
                        "final_labels": ["newsletter"],
                    }
                ],
                scope="sender",
                label="newsletter",
                explanation="",
                storage_items=[],
            )
            store.save_proposal(proposal)

            rejected = store.review_proposal(proposal.id, "rejected", review_notes="Too broad.")

            self.assertEqual(rejected.status, "rejected")
            self.assertEqual(rejected.approved_rule_id, "")

    def test_disable_rule_marks_it_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            rules_memory = TeachableRuleMemory(Path(temp_dir) / "rules.json")
            proposal = build_memory_proposal(
                provider="gmail",
                account_id="founder-test",
                source_batch_id="founder-test-batch-1",
                selected_items=[
                    {
                        "message_id": "g1",
                        "sender": '"Vendor" <vendor@example.com>',
                        "subject": "Quarterly vendor update",
                        "date": "2026-06-28T00:00:00Z",
                        "final_labels": ["newsletter"],
                    }
                ],
                scope="sender",
                label="newsletter",
                explanation="",
                storage_items=[],
            )
            from src.memory_proposal_store import rule_from_memory_proposal

            rule = rules_memory.save_rule(rule_from_memory_proposal(proposal, existing_count=0))
            disabled = rules_memory.disable_rule(rule.id, reason="No longer useful.")

            self.assertFalse(disabled.enabled)
            self.assertEqual(disabled.disabled_reason, "No longer useful.")

    def test_reapproving_approved_proposal_does_not_duplicate_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage_dir = root / "gmail_fetch"
            store = MemoryProposalStore(memory_proposals_path(storage_dir))
            proposal = build_memory_proposal(
                provider="gmail",
                account_id="founder-test",
                source_batch_id="founder-test-batch-1",
                selected_items=[
                    {
                        "message_id": "g1",
                        "sender": '"Vendor" <vendor@example.com>',
                        "subject": "Quarterly vendor update",
                        "date": "2026-06-28T00:00:00Z",
                        "final_labels": ["newsletter"],
                    }
                ],
                scope="sender",
                label="newsletter",
                explanation="",
                storage_items=[],
            )
            store.save_proposal(proposal)
            rules_memory = TeachableRuleMemory(storage_dir / "teachable_classification_rules.json")

            approved_once = store.review_proposal(proposal.id, "approved", rules_memory=rules_memory, review_notes="First.")
            approved_twice = store.review_proposal(proposal.id, "approved", rules_memory=rules_memory, review_notes="Second.")

            self.assertEqual(approved_once.approved_rule_id, approved_twice.approved_rule_id)
            self.assertEqual(len(rules_memory.list_rules()), 1)

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
