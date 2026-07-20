import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicDemoTests(unittest.TestCase):
    def test_demo_is_self_contained_and_explicitly_synthetic(self) -> None:
        page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "docs" / "demo" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Synthetic demo", page)
        self.assertIn("No login or inbox access", page)
        self.assertIn("cannot change an inbox", page)
        self.assertIn("@example.test", script)

    def test_demo_has_no_network_capability(self) -> None:
        script = (ROOT / "docs" / "demo" / "app.js").read_text(encoding="utf-8")

        for network_primitive in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource"):
            self.assertNotIn(network_primitive, script)

    def test_demo_brand_assets_exist(self) -> None:
        self.assertTrue((ROOT / "docs" / "assets" / "brand" / "threadwise-primary-logo.png").is_file())
        self.assertTrue((ROOT / "docs" / "assets" / "brand" / "threadwise-app-icon.png").is_file())


if __name__ == "__main__":
    unittest.main()
