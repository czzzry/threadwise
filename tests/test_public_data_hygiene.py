import unittest
from pathlib import Path

from scripts.check_public_data_hygiene import ROOT, is_reserved_domain, scan_text


class PublicDataHygieneTests(unittest.TestCase):
    def test_reserved_demo_domains_are_allowed(self) -> None:
        self.assertTrue(is_reserved_domain("example.com"))
        self.assertTrue(is_reserved_domain("mail.example"))
        self.assertTrue(is_reserved_domain("example.test"))
        self.assertTrue(is_reserved_domain("example.invalid"))

    def test_real_domain_is_rejected_in_public_demo(self) -> None:
        path = ROOT / "examples/gmail_companion_demo/message.json"

        violations = scan_text(path, '{"sender": "alerts@real-provider.com"}')

        self.assertTrue(any("non-reserved demo email domain" in item for item in violations))

    def test_live_founder_evidence_marker_is_rejected(self) -> None:
        path = ROOT / "docs/handoff/example.md"

        violations = scan_text(path, "The live founder Gmail inbox contained 100 messages.")

        self.assertTrue(any("unsanitized live-account evidence" in item for item in violations))

    def test_qa_documents_require_a_data_classification(self) -> None:
        path = ROOT / "docs/qa/example.md"

        violations = scan_text(path, "# Synthetic QA\n")

        self.assertTrue(any("missing QA data classification" in item for item in violations))


if __name__ == "__main__":
    unittest.main()
