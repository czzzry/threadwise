import io
import json
import tempfile
import unittest
from pathlib import Path

from src.runtime_cascade_cli import main


class FakeRuntimeCascadeClient:
    def analyze_message(self, payload: dict) -> dict:
        return {
            "labels": ["newsletter"] if payload["sender"] == "Utopia" else [],
            "confidence": "medium",
            "rationale": "Stub.",
            "unresolved": payload["sender"] != "Utopia",
        }


class RuntimeCascadeCliTests(unittest.TestCase):
    def test_cli_runs_runtime_cascade_with_cluster_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outlook_dir = root / "outlookmail_fetch"
            (root / "gmail_fetch" / "batches").mkdir(parents=True, exist_ok=True)
            (root / "protonmail_fetch" / "batches").mkdir(parents=True, exist_ok=True)
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Utopia",
                        "subject": "Utopia Age 113 - Age of Merry Mayhems",
                        "snippet": "Update.",
                        "body": "Update.",
                    }
                ],
            )
            rules_path = root / "accepted_shadow_teachable_rules.json"
            rules_path.write_text(json.dumps({"rules": []}, indent=2))
            pack_path = root / "cluster-pack.json"
            pack_path.write_text(
                json.dumps(
                    {
                        "preference_reviews": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "utopia",
                                "memory_seed": {"cluster_policy_key": "outlookmail:utopia"},
                            }
                        ]
                    },
                    indent=2,
                )
            )
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--output-storage-dir",
                    str(root),
                    "--gmail-storage-dir",
                    str(root / "gmail_fetch"),
                    "--protonmail-storage-dir",
                    str(root / "protonmail_fetch"),
                    "--outlookmail-storage-dir",
                    str(outlook_dir),
                    "--accepted-shadow-rules-path",
                    str(rules_path),
                    "--cluster-decision-pack-path",
                    str(pack_path),
                    "--llm-model",
                    "fake-model",
                ],
                stdout=stdout,
                cwd=root,
                llm_client_factory=lambda _model: FakeRuntimeCascadeClient(),
            )

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertIn("Runtime cascade: messages=1 | resolved=1 | unresolved=0", output)
            self.assertIn("LLM=1", output)
            self.assertIn("Safety memory hits=0", output)
            self.assertIn("Safety lane: security-sensitive=0 | suspicious=0 | total caution=0", output)
            saved_files = list((root / "runtime_cascades").glob("*.json"))
            self.assertEqual(len(saved_files), 1)
            payload = json.loads(saved_files[0].read_text())
            outcome = payload["providers"]["outlookmail"]["outcomes"][0]
            self.assertEqual(outcome["decision_provenance"]["decision_source"], "llm-escalation")
            self.assertEqual(
                outcome["decision_provenance"]["retrieved_memory_keys"],
                ["outlookmail:utopia"],
            )

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
