import unittest

from src.label_taxonomy import allowed_gmail_labels, gmail_label_name


class LabelTaxonomyTest(unittest.TestCase):
    def test_reply_needed_uses_needs_action_display_label(self) -> None:
        self.assertEqual(gmail_label_name("reply-needed"), "EA/NeedsAction")

    def test_suspicious_is_an_allowed_gmail_label(self) -> None:
        self.assertEqual(gmail_label_name("suspicious"), "EA/Suspicious")
        self.assertIn("EA/Suspicious", allowed_gmail_labels())


if __name__ == "__main__":
    unittest.main()
