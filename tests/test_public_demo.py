import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicDemoTests(unittest.TestCase):
    def test_demo_is_self_contained_and_explicitly_synthetic(self) -> None:
        page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "docs" / "demo" / "app.js").read_text(encoding="utf-8")
        model = (ROOT / "docs" / "demo" / "model.mjs").read_text(encoding="utf-8")

        self.assertIn("Synthetic demo", page)
        self.assertIn("No login or inbox access", page)
        self.assertIn("cannot change an inbox", page)
        self.assertIn("@example.test", model)

    def test_demo_has_no_network_capability(self) -> None:
        script = (ROOT / "docs" / "demo" / "app.js").read_text(encoding="utf-8")
        model = (ROOT / "docs" / "demo" / "model.mjs").read_text(encoding="utf-8")

        for network_primitive in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource"):
            self.assertNotIn(network_primitive, script + model)

    def test_demo_brand_assets_exist(self) -> None:
        page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")

        self.assertTrue((ROOT / "docs" / "assets" / "brand" / "threadwise-primary-logo.png").is_file())
        self.assertTrue((ROOT / "docs" / "assets" / "brand" / "threadwise-app-icon.png").is_file())
        self.assertIn('<link rel="icon" href="assets/brand/threadwise-app-icon.png">', page)

    def test_demo_scopes_validates_and_preserves_the_guided_teaching_flow(self) -> None:
        script = (ROOT / "docs" / "demo" / "app.js").read_text(encoding="utf-8")
        model = (ROOT / "docs" / "demo" / "model.mjs").read_text(encoding="utf-8")

        self.assertIn("teaching: roleScoutTeaching", model)
        self.assertIn('data-action="open-guided-teaching"', script)
        self.assertIn('data-action="keep-discussing"', script)
        self.assertIn("state.teachingNote = note.value", script)
        self.assertIn("normalizeTeachingNote", script)
        self.assertIn("state.teachingError", script)
        self.assertIn('aria-invalid="${Boolean(state.teachingError)}"', script)
        self.assertNotIn('data-action="cancel">Keep discussing', script)

    def test_demo_preserves_focus_and_acknowledges_positive_feedback(self) -> None:
        script = (ROOT / "docs" / "demo" / "app.js").read_text(encoding="utf-8")

        self.assertEqual(script.count("renderMessages();"), 1)
        self.assertIn("updateInboxVisualState()", script)
        self.assertIn("updateMessageSelection()", script)
        self.assertIn("focusCompanion(focusSelector)", script)
        self.assertIn('state.mode = "acknowledged"', script)
        self.assertIn("Decision confirmed.", script)

    def test_demo_distinguishes_future_only_from_existing_message_changes(self) -> None:
        script = (ROOT / "docs" / "demo" / "app.js").read_text(encoding="utf-8")
        model = (ROOT / "docs" / "demo" / "model.mjs").read_text(encoding="utf-8")

        self.assertIn('state.receiptAction = "future-only"', script)
        self.assertIn("Future lesson saved.", script)
        self.assertIn("Existing demo messages remain unchanged", script)
        self.assertIn('state.receiptAction = "apply-matches"', script)
        self.assertIn("saveTeachingForFuture", script)
        self.assertIn("applyTeachingToMatches", script)
        self.assertIn("matchingMessagesNeedingUpdate", script)
        self.assertIn("Future rule saved · existing inbox unchanged", model)
        self.assertIn("Future rule already saved · existing inbox unchanged", model)

    def test_demo_renders_labels_and_derived_mailbox_counts(self) -> None:
        page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "docs" / "demo" / "app.js").read_text(encoding="utf-8")
        model = (ROOT / "docs" / "demo" / "model.mjs").read_text(encoding="utf-8")
        styles = (ROOT / "docs" / "demo" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('type="module"', page)
        self.assertIn('data-folder-count="EA/Work"', page)
        self.assertIn('data-folder-count="EA/Promotions"', page)
        self.assertIn('id="mailbox-status"', page)
        self.assertIn('data-message-label', script)
        self.assertIn('data-confirmed', script)
        self.assertIn('.confirmed-badge[hidden]', styles)
        self.assertEqual(model.count("matchKey: roleScoutTeaching.matchKey"), 4)


if __name__ == "__main__":
    unittest.main()
