import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.local_environment import load_local_environment


class LocalEnvironmentTests(unittest.TestCase):
    def test_loads_private_repo_environment_without_overwriting_process_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / ".env").write_text(
                "POSTHOG_PROJECT_TOKEN=phc_from_file\n"
                "POSTHOG_HOST=https://eu.i.posthog.com\n"
                "THREADWISE_ANALYTICS_ENABLED=true\n"
            )

            with patch.dict(os.environ, {"POSTHOG_PROJECT_TOKEN": "phc_from_process"}, clear=True):
                loaded = load_local_environment(repo_root)

                self.assertEqual(os.environ["POSTHOG_PROJECT_TOKEN"], "phc_from_process")
                self.assertEqual(os.environ["POSTHOG_HOST"], "https://eu.i.posthog.com")
                self.assertEqual(os.environ["THREADWISE_ANALYTICS_ENABLED"], "true")
                self.assertEqual(loaded, {"POSTHOG_HOST", "THREADWISE_ANALYTICS_ENABLED"})


if __name__ == "__main__":
    unittest.main()
