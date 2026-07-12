import json
import tempfile
import unittest
from pathlib import Path

from src.safety_backlog_report import build_safety_backlog_report


class SafetyBacklogReportTests(unittest.TestCase):
    def test_build_report_aggregates_dispositions_across_provider_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            proton_dir = root / "protonmail"
            self._write_dispositions(
                gmail_dir,
                [
                    {"id": "gmail-approved", "provider": "gmail", "status": "approved"},
                    {"id": "gmail-pending", "provider": "gmail", "status": "pending"},
                ],
            )
            self._write_dispositions(
                proton_dir,
                [
                    {"id": "proton-rejected", "provider": "protonmail", "status": "rejected"},
                ],
            )

            report = build_safety_backlog_report(
                provider_storage_dirs=[
                    ("gmail", gmail_dir),
                    ("protonmail", proton_dir),
                ],
                report={
                    "providers": {
                        "gmail": {"safety_memory_projection": {"projected": {"heuristic_false_hide_risk_count": 1}}},
                        "protonmail": {"safety_memory_projection": {"projected": {"heuristic_false_hide_risk_count": 2}}},
                    }
                },
                frontier_plan={"summary": {"safety_priority_clusters": 3}},
                cluster_pack={"summary": {"safety_priority_review_count": 4}},
                review_pack={"summary": {"safety_priority_review_count": 5}},
                digest={"top_targets": [{"provider": "gmail"}, {"provider": "protonmail"}]},
            )

            self.assertEqual(report["summary"]["approved_disposition_count"], 1)
            self.assertEqual(report["summary"]["pending_disposition_count"], 1)
            self.assertEqual(report["summary"]["rejected_disposition_count"], 1)
            self.assertEqual(report["summary"]["top_target_count"], 2)
            self.assertEqual(report["summary"]["backlog_pressure"], "manageable")
            self.assertEqual(report["provider_summaries"]["gmail"]["approved_disposition_count"], 1)
            self.assertEqual(report["provider_summaries"]["gmail"]["pending_disposition_count"], 1)
            self.assertEqual(report["provider_summaries"]["protonmail"]["rejected_disposition_count"], 1)
            self.assertEqual(report["provider_summaries"]["gmail"]["top_target_count"], 1)
            self.assertEqual(report["provider_drivers"][0]["provider"], "gmail")

    def _write_dispositions(self, storage_dir: Path, dispositions: list[dict]) -> None:
        storage_dir.mkdir(parents=True, exist_ok=True)
        normalized = []
        for disposition in dispositions:
            normalized.append(
                {
                    "id": disposition["id"],
                    "provider": disposition["provider"],
                    "account_id": "founder-test",
                    "source_batch_id": "batch-1",
                    "source_message_ids": ["m1"],
                    "scope": "sender",
                    "disposition": "phishing",
                    "source_examples": [],
                    "explanation": "",
                    "preview": {"match_count": 0, "matches": []},
                    "status": disposition["status"],
                    "created_at": "2026-06-28T00:00:00Z",
                    "updated_at": "2026-06-28T00:00:00Z",
                    "review_notes": "",
                }
            )
        (storage_dir / "safety_dispositions.json").write_text(
            json.dumps(
                {
                    "status": "PROTOTYPE - local safety review dispositions",
                    "generated_at": "2026-06-28T00:00:00Z",
                    "disposition_count": len(normalized),
                    "dispositions": normalized,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
