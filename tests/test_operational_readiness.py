import json
import tempfile
import unittest
from pathlib import Path

from src.operational_readiness import build_operational_readiness_report


class OperationalReadinessTests(unittest.TestCase):
    def test_build_report_warns_when_not_enough_runs_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            self._write_runtime_report(
                output_dir,
                "runtime-cascade-1",
                message_count=100,
                unresolved_count=10,
                safety_review_count=4,
                accepted_memory_count=30,
                deterministic_count=60,
                llm_escalation_count=0,
            )

            report = build_operational_readiness_report(output_dir, window=5)

            self.assertEqual(report["overall_status"], "WARN")
            self.assertIn("Fewer than 3 recent runs", " ".join(report["reasons"]))

    def test_build_report_passes_for_stable_recent_runs_with_low_queue_debt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            for index, unresolved in enumerate((12, 11, 10), start=1):
                self._write_runtime_report(
                    output_dir,
                    f"runtime-cascade-{index}",
                    message_count=100,
                    unresolved_count=unresolved,
                    safety_review_count=4,
                    accepted_memory_count=35,
                    deterministic_count=53,
                    llm_escalation_count=2,
                )
            self._write_queue(output_dir, pending_count=20, founder_question_count=2)
            self._write_founder_application(output_dir, "application-1", resolved_gain=6)

            report = build_operational_readiness_report(output_dir, window=5)

            self.assertEqual(report["overall_status"], "PASS")
            self.assertIn("stable enough", " ".join(report["reasons"]))

    def test_build_report_pauses_when_queue_and_unresolved_pressure_are_too_high(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            for index, unresolved in enumerate((30, 32, 35), start=1):
                self._write_runtime_report(
                    output_dir,
                    f"runtime-cascade-{index}",
                    message_count=100,
                    unresolved_count=unresolved,
                    safety_review_count=14,
                    accepted_memory_count=20,
                    deterministic_count=45,
                    llm_escalation_count=1,
                )
            self._write_queue(output_dir, pending_count=230, founder_question_count=11)

            report = build_operational_readiness_report(output_dir, window=5)

            self.assertEqual(report["overall_status"], "PAUSE")
            joined = " ".join(report["reasons"])
            self.assertIn("too high", joined)
            self.assertIn("operator debt", joined)

    def _write_runtime_report(
        self,
        output_dir: Path,
        run_id: str,
        *,
        message_count: int,
        unresolved_count: int,
        safety_review_count: int,
        accepted_memory_count: int,
        deterministic_count: int,
        llm_escalation_count: int,
    ) -> None:
        runtime_dir = output_dir / "runtime_cascades"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        resolved_count = message_count - unresolved_count
        (runtime_dir / f"{run_id}.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-06-29T00:00:00Z",
                    "summary": {
                        "message_count": message_count,
                        "resolved_count": resolved_count,
                        "unresolved_count": unresolved_count,
                        "accepted_memory_count": accepted_memory_count,
                        "deterministic_count": deterministic_count,
                        "llm_escalation_count": llm_escalation_count,
                        "safety_review_count": safety_review_count,
                    },
                },
                indent=2,
            )
        )

    def _write_queue(self, output_dir: Path, *, pending_count: int, founder_question_count: int) -> None:
        (output_dir / "unified_review_queue.json").write_text(
            json.dumps(
                {
                    "summary": {
                        "pending_count": pending_count,
                        "pending_by_type": {"founder-question": founder_question_count},
                        "provider_counts": {"gmail": pending_count},
                    }
                },
                indent=2,
            )
        )

    def _write_founder_application(self, output_dir: Path, app_id: str, *, resolved_gain: int) -> None:
        applications_dir = output_dir / "founder_answer_applications"
        applications_dir.mkdir(parents=True, exist_ok=True)
        (applications_dir / f"{app_id}.json").write_text(
            json.dumps(
                {
                    "question_id": "question-1",
                    "impact_delta": {"resolved_gain": resolved_gain},
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
