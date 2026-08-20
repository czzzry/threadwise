import unittest

from scripts.export_threadwise_marketing_fixture import SOURCE_DIR, provider_fixture


def string_values(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "contract_version":
                continue
            yield from string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from string_values(child)
    elif isinstance(value, str):
        yield value


class MarketingFixtureExportTests(unittest.TestCase):
    def test_provider_fixtures_do_not_mutate_the_source_demo(self) -> None:
        before = sorted(path.relative_to(SOURCE_DIR) for path in SOURCE_DIR.rglob("*"))

        provider_fixture("gmail")
        provider_fixture("protonmail")

        after = sorted(path.relative_to(SOURCE_DIR) for path in SOURCE_DIR.rglob("*"))
        self.assertEqual(before, after)

    def test_proton_fixture_contains_no_gmail_display_language(self) -> None:
        fixture = provider_fixture("protonmail")

        self.assertEqual("protonmail", fixture["selected_context"]["provider"])
        self.assertFalse(
            [value for value in string_values(fixture) if "gmail" in value.lower()]
        )


if __name__ == "__main__":
    unittest.main()
