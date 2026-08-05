import io
import json
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from src.threadwise_startup import (
    HEALTH_SERVICE_ID,
    LAUNCH_AGENT_LABEL,
    build_proton_bridge_status,
    build_proton_daily_launch_agent_plist,
    build_status_report,
    bootstrap_launch_agent,
    install_launch_agent,
    probe_health,
    render_launch_agent_plist,
    start_launch_agent,
    stop_launch_agent,
    uninstall_launch_agent,
)


class ThreadwiseStartupTests(unittest.TestCase):
    def test_bootstrap_retries_while_launchd_finishes_bootout(self) -> None:
        plist_path = Path("/tmp/com.threadwise.companion.plist")
        with (
            patch(
                "src.threadwise_startup.subprocess.run",
                side_effect=[subprocess.CalledProcessError(5, "launchctl"), None],
            ) as run_mock,
            patch("src.threadwise_startup.time.sleep") as sleep_mock,
        ):
            bootstrap_launch_agent(plist_path, uid="501")

        self.assertEqual(run_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0.5)

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

    def test_proton_daily_launch_agent_runs_incrementally_at_six(self) -> None:
        repo_root = Path("/Users/example/threadwise")
        log_dir = Path("/Users/example/Library/Logs/Threadwise")

        payload = build_proton_daily_launch_agent_plist(
            repo_root,
            python_executable="/opt/python/bin/python3",
            log_dir=log_dir,
        )

        self.assertEqual(payload["Label"], "com.threadwise.proton-daily")
        self.assertFalse(payload["RunAtLoad"])
        self.assertFalse(payload["KeepAlive"])
        self.assertEqual(payload["StartCalendarInterval"], {"Hour": 6, "Minute": 0})
        self.assertEqual(
            payload["ProgramArguments"],
            [
                "/opt/python/bin/python3",
                str(repo_root / "scripts" / "daily_live_protonmail_run.py"),
                "--account-id",
                "founder-proton",
                "--batch-size",
                "25",
            ],
        )
        self.assertEqual(payload["StandardOutPath"], str(log_dir / "proton-daily.out.log"))
        self.assertEqual(payload["StandardErrorPath"], str(log_dir / "proton-daily.err.log"))

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
                    ["launchctl", "enable", "gui/501/com.threadwise.companion"],
                    ["launchctl", "bootout", "gui/501/com.threadwise.companion"],
                    ["launchctl", "bootstrap", "gui/501", str(plist_path)],
                    ["launchctl", "enable", "gui/501/com.threadwise.proton-daily"],
                    ["launchctl", "bootout", "gui/501/com.threadwise.proton-daily"],
                    [
                        "launchctl",
                        "bootstrap",
                        "gui/501",
                        str(plist_path.with_name("com.threadwise.proton-daily.plist")),
                    ],
                ],
            )
            self.assertEqual(
                [call.kwargs["check"] for call in run_mock.call_args_list],
                [True, False, True, True, False, True],
            )

    def test_stop_disables_before_unloading_and_preserves_the_plist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plist_path = Path(temp_dir) / "com.threadwise.companion.plist"
            plist_path.write_text("plist")
            with (
                patch("src.threadwise_startup.platform.system", return_value="Darwin"),
                patch("src.threadwise_startup.subprocess.check_output", return_value="501\n"),
                patch("src.threadwise_startup.subprocess.run") as run_mock,
            ):
                result = stop_launch_agent(plist_path=plist_path)

            self.assertTrue(plist_path.exists())
            self.assertEqual(result["state"], "stopped")
            self.assertEqual(
                [call.args[0] for call in run_mock.call_args_list],
                [
                    ["launchctl", "disable", "gui/501/com.threadwise.companion"],
                    ["launchctl", "disable", "gui/501/com.threadwise.proton-daily"],
                    ["launchctl", "bootout", "gui/501/com.threadwise.companion"],
                    ["launchctl", "bootout", "gui/501/com.threadwise.proton-daily"],
                ],
            )
            self.assertEqual(
                [call.kwargs["check"] for call in run_mock.call_args_list],
                [True, True, False, False],
            )

    def test_start_reenables_and_bootstraps_the_preserved_plist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            plist_path = repo_root / "com.threadwise.companion.plist"
            plist_path.write_text("plist")
            with (
                patch("src.threadwise_startup.platform.system", return_value="Darwin"),
                patch("src.threadwise_startup.subprocess.check_output", return_value="501\n"),
                patch("src.threadwise_startup.subprocess.run") as run_mock,
                patch("src.threadwise_startup.launch_agent_is_loaded", return_value=False),
            ):
                result = start_launch_agent(repo_root, plist_path=plist_path)

            self.assertEqual(result["state"], "starting")
            self.assertEqual(
                [call.args[0] for call in run_mock.call_args_list],
                [
                    ["launchctl", "enable", "gui/501/com.threadwise.companion"],
                    ["launchctl", "bootstrap", "gui/501", str(plist_path)],
                    ["launchctl", "enable", "gui/501/com.threadwise.proton-daily"],
                    [
                        "launchctl",
                        "bootstrap",
                        "gui/501",
                        str(plist_path.with_name("com.threadwise.proton-daily.plist")),
                    ],
                ],
            )

    def test_start_kickstarts_an_already_loaded_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            plist_path = repo_root / "com.threadwise.companion.plist"
            plist_path.write_text("plist")
            with (
                patch("src.threadwise_startup.platform.system", return_value="Darwin"),
                patch("src.threadwise_startup.subprocess.check_output", return_value="501\n"),
                patch("src.threadwise_startup.subprocess.run") as run_mock,
                patch("src.threadwise_startup.launch_agent_is_loaded", return_value=True),
            ):
                start_launch_agent(repo_root, plist_path=plist_path)

            self.assertEqual(
                [call.args[0] for call in run_mock.call_args_list],
                [
                    ["launchctl", "enable", "gui/501/com.threadwise.companion"],
                    ["launchctl", "kickstart", "-k", "gui/501/com.threadwise.companion"],
                    ["launchctl", "enable", "gui/501/com.threadwise.proton-daily"],
                ],
            )

    def test_build_status_report_uses_health_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            plist_path = repo_root / "com.threadwise.companion.plist"
            plist_path.write_text("plist")

            with (
                patch("src.threadwise_startup.probe_health") as probe_mock,
                patch("src.threadwise_startup.inspect_launch_agent") as launch_agent_mock,
                patch("src.threadwise_startup.build_proton_bridge_status") as bridge_mock,
            ):
                probe_mock.return_value = {
                    "kind": "wrong-service",
                    "label": "Wrong service on port",
                    "details": "Something else is responding.",
                    "service_id": "other-service",
                    "service_name": "Other Service",
                    "health_path": "/api/health",
                }
                launch_agent_mock.return_value = {"loaded": True, "disabled": False}
                bridge_mock.return_value = {"state": "not-configured"}
                report = build_status_report(repo_root, plist_path=plist_path, origin="http://127.0.0.1:8021")

            self.assertTrue(report["plist_exists"])
            self.assertEqual(report["state"], "needs-attention")
            self.assertEqual(report["health"]["kind"], "wrong-service")
            self.assertEqual(report["health"]["service_id"], "other-service")
            self.assertEqual(report["service_id"], HEALTH_SERVICE_ID)

    def test_status_report_distinguishes_running_and_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            with (
                patch("src.threadwise_startup.inspect_launch_agent", return_value={"loaded": True, "disabled": False}),
                patch("src.threadwise_startup.probe_health", return_value={"kind": "ready", "reachable": True}),
                patch("src.threadwise_startup.build_proton_bridge_status", return_value={"state": "available"}),
            ):
                running = build_status_report(repo_root)
            with (
                patch("src.threadwise_startup.inspect_launch_agent", return_value={"loaded": False, "disabled": True}),
                patch("src.threadwise_startup.probe_health", return_value={"kind": "helper-unreachable", "reachable": False}),
                patch("src.threadwise_startup.build_proton_bridge_status", return_value={"state": "available"}),
            ):
                stopped = build_status_report(repo_root)

        self.assertEqual(running["state"], "running")
        self.assertEqual(running["state_label"], "Running")
        self.assertEqual(stopped["state"], "stopped")
        self.assertEqual(stopped["state_label"], "Stopped")

    def test_status_report_exposes_the_proton_daily_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)

            def inspect(*, uid=None, label=LAUNCH_AGENT_LABEL):
                return {
                    "loaded": True,
                    "disabled": False,
                    "target": f"gui/501/{label}",
                }

            with (
                patch("src.threadwise_startup.inspect_launch_agent", side_effect=inspect),
                patch("src.threadwise_startup.probe_health", return_value={"kind": "ready", "reachable": True}),
                patch("src.threadwise_startup.build_proton_bridge_status", return_value={"state": "available"}),
            ):
                report = build_status_report(repo_root)

        self.assertEqual(report["proton_daily"]["state"], "scheduled")
        self.assertEqual(report["proton_daily"]["state_label"], "Scheduled daily at 6:00")

    def test_bridge_status_reports_required_but_unavailable_without_reading_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            config_path = (
                repo_root
                / "data"
                / "protonmail_credentials"
                / "protonmail_bridge"
                / "founder-proton.json"
            )
            config_path.parent.mkdir(parents=True)
            config_path.write_text("do-not-read")
            app_path = repo_root / "Proton Mail Bridge.app"
            app_path.mkdir()

            with patch("src.threadwise_startup.proton_bridge_is_running", return_value=False):
                status = build_proton_bridge_status(
                    repo_root,
                    app_path=app_path,
                )

            self.assertTrue(status["required"])
            self.assertEqual(status["state"], "unavailable")
            self.assertIn("Open Proton Mail Bridge", status["details"])

    def test_bridge_status_is_optional_when_no_bridge_config_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            status = build_proton_bridge_status(repo_root)

        self.assertFalse(status["required"])
        self.assertEqual(status["state"], "not-configured")

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
