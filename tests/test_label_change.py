import unittest

from src.label_change import LabelChangeError, normalize_label_change, require_current_baseline


class LabelChangeTests(unittest.TestCase):
    def change(self, operation, before, targets=(), sources=()):
        return normalize_label_change({
            "operation": operation,
            "labels_before": list(before),
            "target_labels": list(targets),
            "source_labels": list(sources),
            "interpretation": {"source": "manual", "status": "reviewed"},
        })

    def test_only_add_remove_and_replace_preserve_order(self):
        self.assertEqual(self.change("only", ["travel"], ["shopping-order", "receipt-billing"]).labels_after, ("shopping-order", "receipt-billing"))
        self.assertEqual(self.change("add", ["shopping-order"], ["receipt-billing"]).labels_after, ("shopping-order", "receipt-billing"))
        self.assertEqual(self.change("remove", ["financial-account", "reply-needed"], sources=["reply-needed"]).labels_after, ("financial-account",))
        self.assertEqual(self.change("replace", ["newsletter", "travel", "personal"], ["account-security"], ["newsletter", "travel"]).labels_after, ("account-security", "personal"))

    def test_invalid_noop_empty_unknown_duplicate_and_over_cap_stop(self):
        invalid = [
            {"operation": "add", "labels_before": ["travel"], "target_labels": ["travel"]},
            {"operation": "remove", "labels_before": ["travel"], "source_labels": ["travel"]},
            {"operation": "only", "labels_before": [], "target_labels": ["not-real"]},
            {"operation": "only", "labels_before": [], "target_labels": ["travel", "travel"]},
            {"operation": "add", "labels_before": ["travel", "personal", "newsletter"], "target_labels": ["reply-needed"]},
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(LabelChangeError):
                normalize_label_change(payload)

    def test_stale_baseline_stops_apply(self):
        change = self.change("add", ["shopping-order"], ["receipt-billing"])
        with self.assertRaisesRegex(LabelChangeError, "changed after the preview"):
            require_current_baseline(change, ["shopping-order", "reply-needed"])


if __name__ == "__main__":
    unittest.main()
