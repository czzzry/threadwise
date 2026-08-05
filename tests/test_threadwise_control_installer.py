import plistlib
import tempfile
import unittest
from pathlib import Path

from src.threadwise_control_installer import (
    CONTROL_APP_NAME,
    CONTROL_BUNDLE_ID,
    CONTROL_LAUNCH_AGENT_LABEL,
    build_control_config,
    build_control_info_plist,
    build_control_launch_agent_plist,
    exact_process_match,
    install_control_app,
)


class ThreadwiseControlInstallerTests(unittest.TestCase):
    def test_info_plist_builds_a_menu_bar_only_app(self) -> None:
        payload = build_control_info_plist()

        self.assertEqual(payload["CFBundleIdentifier"], CONTROL_BUNDLE_ID)
        self.assertEqual(payload["CFBundleExecutable"], CONTROL_APP_NAME)
        self.assertTrue(payload["LSUIElement"])

    def test_control_launch_agent_starts_at_login_without_keepalive(self) -> None:
        app_path = Path("/Users/example/Applications/Threadwise Control.app")
        payload = build_control_launch_agent_plist(app_path, log_dir=Path("/tmp/logs"))

        self.assertEqual(payload["Label"], CONTROL_LAUNCH_AGENT_LABEL)
        self.assertTrue(payload["RunAtLoad"])
        self.assertFalse(payload["KeepAlive"])
        self.assertEqual(
            payload["ProgramArguments"],
            [str(app_path / "Contents" / "MacOS" / CONTROL_APP_NAME)],
        )

    def test_control_config_points_to_existing_manager_without_moving_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            config = build_control_config(repo_root, python_executable="/opt/python3")

        self.assertEqual(config["repoRoot"], str(repo_root.resolve()))
        self.assertEqual(config["pythonExecutable"], "/opt/python3")
        self.assertEqual(
            config["managerScript"],
            str((repo_root / "scripts" / "manage_threadwise_startup.py").resolve()),
        )
        self.assertNotIn("dataPath", config)

    def test_dry_run_does_not_build_or_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            source_path = repo_root / "macos" / "ThreadwiseControl" / "ThreadwiseControl.swift"
            source_path.parent.mkdir(parents=True)
            source_path.write_text("source")

            result = install_control_app(repo_root, dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertFalse(result["installed"])

    def test_existing_control_lookup_matches_only_the_exact_executable(self) -> None:
        executable = Path("/Users/example/Applications/Threadwise Control.app/Contents/MacOS/Threadwise Control")

        pattern = exact_process_match(executable)

        self.assertTrue(pattern.startswith("^"))
        self.assertTrue(pattern.endswith("$"))
        self.assertIn(r"Threadwise\ Control", pattern)


if __name__ == "__main__":
    unittest.main()
