import unittest
from pathlib import Path

from scripts.check_public_data_hygiene import ROOT, is_reserved_domain, scan_text


def credential_fixture(*parts: str) -> str:
    """Build detector inputs without committing credential-shaped literals."""
    return "".join(parts)


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

    def test_machine_home_fixture_exemption_is_path_scoped(self) -> None:
        fixture_path = ROOT / "tests/test_threadwise_startup.py"
        ordinary_path = ROOT / "docs/setup.md"

        self.assertEqual([], scan_text(fixture_path, 'Path("/Users/example/threadwise")'))
        violations = scan_text(ordinary_path, 'Path("/Users/example/threadwise")')

        self.assertTrue(any("machine-specific home path" in item for item in violations))

    def test_machine_home_fixture_exemption_does_not_exempt_secrets(self) -> None:
        path = ROOT / "tests/test_threadwise_startup.py"
        secret = credential_fixture("s", "k", "-", "A" * 32)

        violations = scan_text(path, f'OPENAI_API_KEY="{secret}"')

        self.assertTrue(any("OpenAI API key" in item for item in violations))

    def test_qa_documents_require_a_data_classification(self) -> None:
        path = ROOT / "docs/qa/example.md"

        violations = scan_text(path, "# Synthetic QA\n")

        self.assertTrue(any("missing QA data classification" in item for item in violations))

    def test_openai_api_keys_are_rejected(self) -> None:
        path = ROOT / "src/example.py"
        secrets = (
            credential_fixture("s", "k", "-", "A" * 32),
            credential_fixture("s", "k", "-proj-", "A" * 32, "-"),
            credential_fixture("s", "k", "-svcacct-", "A" * 32, "-"),
        )

        for secret in secrets:
            with self.subTest(secret=secret[:12]):
                violations = scan_text(path, f'OPENAI_API_KEY = "{secret}"')
                self.assertTrue(any("OpenAI API key" in item for item in violations))

    def test_google_credentials_and_tokens_are_rejected(self) -> None:
        path = ROOT / "config/example.json"
        cases = {
            "Google API key": credential_fixture("AI", "za", "Sy", "A" * 33),
            "Google OAuth client ID": credential_fixture(
                "123456789012", "-", "a" * 32, ".apps.googleusercontent.com"
            ),
            "Google OAuth client secret": credential_fixture("GOC", "SPX-", "A" * 32),
            "Google OAuth access token": credential_fixture("ya", "29.", "A" * 32),
            "Google OAuth refresh token": credential_fixture("1", "//", "A" * 32),
        }

        for label, secret in cases.items():
            with self.subTest(label=label):
                violations = scan_text(path, f'{{"credential": "{secret}"}}')
                self.assertTrue(any(label in item for item in violations))

    def test_documentation_placeholders_are_allowed(self) -> None:
        path = ROOT / "docs/setup.md"
        placeholders = (
            "sk-proj-...",
            "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789",
            "AIza-your-api-key-here",
            "GOCSPX-your-client-secret-here",
            "ya29.REDACTED",
            "1//YOUR_REFRESH_TOKEN",
            "123456789012-your-client-id.apps.googleusercontent.com",
        )

        for placeholder in placeholders:
            with self.subTest(placeholder=placeholder):
                self.assertEqual([], scan_text(path, f"Example: {placeholder}"))

    def test_secret_containing_example_text_is_still_rejected(self) -> None:
        path = ROOT / "docs/setup.md"
        secret = credential_fixture("s", "k", "-proj-example", "A" * 32)

        violations = scan_text(path, f'OPENAI_API_KEY="{secret}"')

        self.assertTrue(any("OpenAI API key" in item for item in violations))


if __name__ == "__main__":
    unittest.main()
