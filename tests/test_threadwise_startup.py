import io
import json
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from src.threadwise_startup import (
    HEALTH_SERVICE_ID,
    LAUNCH_AGENT_LABEL,
    build_status_report,
    install_launch_agent,
    probe_health,
    render_launch_agent_plist,
    uninstall_launch_agent,
)


class ThreadwiseStartupTests(unittest.TestCase):
    def test_render_launch_agent_plist_targets_repo_root_and_fixed_loopback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            log_dir = repo_root / "logs"

            payload = plistlib.loads(
                render_launch_agent_plist(
                    repo_root,
                    python_executable="/opt/python/bin/python3",
                    log_dir=log_dir,
                )
            )

            self.assertEqual(payload["Label"], LAUNCH_AGENT_LABEL)
            self.assertEqual(
                payload["ProgramArguments"],
                [
                    "/opt/python/bin/python3",
                    str((repo_root / "scripts" / "run_gmail_companion.py").resolve()),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8021",
                ],
            )
            self.assertTrue(payload["RunAtLoad"])
            self.assertTrue(payload["KeepAlive"])
            self.assertEqual(payload["WorkingDirectory"], str(repo_root.resolve()))
            self.assertEqual(payload["StandardOutPath"], str(log_dir / "companion.out.log"))
            self.assertEqual(payload["StandardErrorPath"], str(log_dir / "companion.err.log"))

    def test_install_and_uninstall_commands_support_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            plist_path = repo_root / "com.threadwise.companion.plist"

            install_result = install_launch_agent(repo_root, plist_path=plist_path, dry_run=True)
            self.assertTrue(plist_path.exists())
            self.assertFalse(install_result["launchctl_executed"])

            uninstall_result = uninstall_launch_agent(plist_path=plist_path, dry_run=True)
            self.assertTrue(uninstall_result["removed"])

    def test_install_refreshes_an_existing_launch_agent_before_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            plist_path = repo_root / "com.threadwise.companion.plist"

            with (
                patch("src.threadwise_startup.platform.system", return_value="Darwin"),
                patch("src.threadwise_startup.subprocess.check_output", return_value="501\n"),
                patch("src.threadwise_startup.subprocess.run") as run_mock,
            ):
                result = install_launch_agent(repo_root, plist_path=plist_path)

            self.assertTrue(result["launchctl_executed"])
            self.assertEqual(
                [call.args[0] for call in run_mock.call_args_list],
                [
                    ["launchctl", "bootout", "gui/501/com.threadwise.companion"],
                    ["launchctl", "bootstrap", "gui/501", str(plist_path)],
                ],
            )
            self.assertFalse(run_mock.call_args_list[0].kwargs["check"])
            self.assertTrue(run_mock.call_args_list[1].kwargs["check"])

    def test_build_status_report_uses_health_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            plist_path = repo_root / "com.threadwise.companion.plist"
            plist_path.write_text("plist")

            with patch("src.threadwise_startup.probe_health") as probe_mock:
                probe_mock.return_value = {
                    "kind": "wrong-service",
                    "label": "Wrong service on port",
                    "details": "Something else is responding.",
                    "service_id": "other-service",
                    "service_name": "Other Service",
                    "health_path": "/api/health",
                }
                report = build_status_report(repo_root, plist_path=plist_path, origin="http://127.0.0.1:8021")

            self.assertTrue(report["plist_exists"])
            self.assertEqual(report["health"]["kind"], "wrong-service")
            self.assertEqual(report["health"]["service_id"], "other-service")
            self.assertEqual(report["service_id"], HEALTH_SERVICE_ID)

    def test_probe_health_distinguishes_unreachable_and_wrong_service(self) -> None:
        class _FakeResponse:
            def __init__(self, payload: dict, status: int = 200) -> None:
                self.payload = payload
                self.status = status

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

        with patch("urllib.request.urlopen") as urlopen_mock:
            urlopen_mock.return_value = _FakeResponse(
                {
                    "service_id": "other-service",
                    "service_name": "Other Service",
                    "status": "ready",
                    "health_path": "/api/health",
                }
            )
            wrong_service = probe_health(origin="http://127.0.0.1:8021")
            self.assertEqual(wrong_service["kind"], "wrong-service")

        with patch("urllib.request.urlopen", side_effect=URLError("boom")):
            unreachable = probe_health(origin="http://127.0.0.1:8021")
            self.assertEqual(unreachable["kind"], "helper-unreachable")

    def test_cli_outputs_status_without_installing_by_default(self) -> None:
        from src.threadwise_startup import main

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            plist_path = repo_root / "com.threadwise.companion.plist"
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--plist-path",
                    str(plist_path),
                    "install",
                    "--dry-run",
                ],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Dry run only", stdout.getvalue())
