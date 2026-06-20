import unittest
from pathlib import Path

from src.fixture_classifier import FixtureBatchClassifier
from src.review_loop import FixtureReviewLoop


class FixtureBatchClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        fixtures_dir = Path(__file__).resolve().parent.parent / "examples" / "sample_messages"
        self.classifier = FixtureBatchClassifier(fixtures_dir=fixtures_dir)
        review_fixtures_dir = Path(__file__).resolve().parent.parent / "examples" / "fixture_batches"
        self.review_loop = FixtureReviewLoop(fixtures_dir=review_fixtures_dir)

    def test_classify_fixture_batch_returns_review_ready_items(self) -> None:
        review_queue = self.classifier.classify_fixture_batch("generated-batch")

        self.assertEqual(review_queue["batch_id"], "generated-batch")
        self.assertTrue(review_queue["items"])
        self.assertTrue(
            {
                "message_id",
                "sender",
                "subject",
                "date",
                "interpretation",
                "applied_labels",
                "near_misses",
                "confidence_band",
            }.issubset(set(review_queue["items"][0]))
        )

    def test_classify_fixture_batch_emits_explicit_unlabeled_items_when_no_label_should_apply(self) -> None:
        review_queue = self.classifier.classify_fixture_batch("generated-batch")
        unlabeled_item = next(item for item in review_queue["items"] if item["message_id"] == "raw-005")

        self.assertEqual(unlabeled_item["applied_labels"], [])
        self.assertEqual(unlabeled_item["near_misses"], [])
        self.assertEqual(unlabeled_item["confidence_band"], "low")

    def test_classify_fixture_batch_orders_generated_items_for_review(self) -> None:
        review_queue = self.classifier.classify_fixture_batch("generated-batch")

        self.assertEqual(
            [item["message_id"] for item in review_queue["items"]],
            ["raw-001", "raw-002", "raw-004", "raw-003", "raw-005", "raw-006"],
        )

    def test_classify_fixture_batch_reshapes_incompatible_generated_labels_before_review(self) -> None:
        review_queue = self.classifier.classify_fixture_batch("generated-batch")
        newsletter_item = next(item for item in review_queue["items"] if item["message_id"] == "raw-004")

        self.assertNotIn("promotions", newsletter_item["applied_labels"])
        self.assertIn("promotions", newsletter_item["near_misses"])

    def test_classify_fixture_batch_trims_over_cap_generated_labels_into_near_misses(self) -> None:
        review_queue = self.classifier.classify_fixture_batch("generated-batch")
        capped_item = next(item for item in review_queue["items"] if item["message_id"] == "raw-006")

        self.assertEqual(capped_item["applied_labels"], ["travel", "receipt-billing", "calendar-event"])
        self.assertEqual(capped_item["near_misses"], ["personal"])

    def test_generated_review_queue_can_be_reviewed_through_existing_review_flow(self) -> None:
        review_queue = self.classifier.classify_fixture_batch("generated-batch")
        self.review_loop.load_review_queue(review_queue)

        reviewed_item = self.review_loop.review_message("generated-batch", "raw-001", {"type": "approve"})

        self.assertEqual(reviewed_item["review_state"], "reviewed")
        self.assertEqual(reviewed_item["review_action"], "approve")
        self.assertEqual(reviewed_item["final_labels"], ["reply-needed", "job-related"])

    def test_generated_batch_completion_keeps_summary_and_freeze_behavior(self) -> None:
        review_queue = self.classifier.classify_fixture_batch("generated-batch")
        self.review_loop.load_review_queue(review_queue)
        self.review_loop.review_message("generated-batch", "raw-001", {"type": "approve"})
        self.review_loop.review_message("generated-batch", "raw-003", {"type": "edit", "final_labels": []})
        self.review_loop.review_message("generated-batch", "raw-004", {"type": "reject"})

        summary = self.review_loop.complete_batch("generated-batch")
        reloaded_queue = self.review_loop.load_review_queue(review_queue)
        reviewed_item = next(item for item in reloaded_queue["items"] if item["message_id"] == "raw-001")

        self.assertEqual(summary["reviewed_count"], 3)
        self.assertEqual(summary["labeled_count"], 1)
        self.assertEqual(summary["unlabeled_count"], 2)
        self.assertEqual(summary["per_label_counts"], {"reply-needed": 1, "job-related": 1})
        self.assertEqual(summary["reviewer_label_change_count"], 2)
        self.assertEqual(reviewed_item["review_state"], "reviewed")

        with self.assertRaisesRegex(ValueError, "already been reviewed"):
            self.review_loop.review_message("generated-batch", "raw-001", {"type": "reject"})

    def test_classify_messages_marks_financial_statements_as_financial_account(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Sun Life <sunlife@info.sunlife.ca>",
                    "subject": "Your statement is ready",
                    "body": "View your investment statement online in the Sun Life app.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX"],
                    "list_unsubscribe": None,
                    "precedence": "",
                },
                {
                    "message_id": "gmail-live-002",
                    "sender": "MBNA Notifications <noreply@mbna.ca>",
                    "subject": "Your eStatement is available now",
                    "body": "Your most recent account statement is now available online.",
                    "date": "2026-06-19T08:01:00Z",
                    "gmail_label_ids": ["INBOX"],
                    "list_unsubscribe": None,
                    "precedence": "",
                },
                {
                    "message_id": "gmail-live-003",
                    "sender": "N26 <noreply@n26.com>",
                    "subject": "Neue Transaktion auf deinem Konto",
                    "body": "Deine Karte wurde belastet. Sieh dir die neue Transaktion in der N26 App an.",
                    "date": "2026-06-19T08:02:00Z",
                    "gmail_label_ids": ["INBOX"],
                    "list_unsubscribe": None,
                    "precedence": "",
                },
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["financial-account"])
        self.assertEqual(review_queue["items"][1]["applied_labels"], ["financial-account"])
        self.assertEqual(review_queue["items"][2]["applied_labels"], ["financial-account"])

    def test_classify_messages_marks_password_resets_as_account_security(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "BVG <no-reply.sso3@bvg.de>",
                    "subject": "BVG - Reset password",
                    "body": "To choose a new password, click the button below.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX"],
                    "list_unsubscribe": None,
                    "precedence": "",
                },
                {
                    "message_id": "gmail-live-002",
                    "sender": "Microsoft account team <account-security-noreply@accountprotection.microsoft.com>",
                    "subject": "Your single-use code",
                    "body": "Your single-use code is 123456. Only enter this code on an official website.",
                    "date": "2026-06-19T08:01:00Z",
                    "gmail_label_ids": ["INBOX"],
                    "list_unsubscribe": None,
                    "precedence": "",
                },
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["account-security"])
        self.assertEqual(review_queue["items"][1]["applied_labels"], ["account-security"])

    def test_classify_messages_marks_linkedin_direct_message_digests_as_personal(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Kirth Lammens via LinkedIn <messaging-digest-noreply@linkedin.com>",
                    "subject": "Kirth just messaged you",
                    "body": "You have 1 new message. View message.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_SOCIAL"],
                    "list_unsubscribe": "<https://www.linkedin.com/unsub>",
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["personal"])

    def test_classify_messages_marks_google_drive_share_from_real_person_as_personal(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Sophie Riding (via Google Drive)" <drive-shares-dm-noreply@google.com>',
                    "subject": 'Folder shared with you: "Bike trips 2026"',
                    "body": "Sophie Riding shared a folder with you in Google Drive.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["personal"])

    def test_classify_messages_does_not_mark_linkedin_job_alerts_as_personal(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
                    "subject": "Product Manager at Example Corp",
                    "body": "Jobs like this are expiring soon. See more details.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_SOCIAL"],
                    "list_unsubscribe": "<https://www.linkedin.com/unsub>",
                    "precedence": "",
                }
            ],
        )

        self.assertNotIn("personal", review_queue["items"][0]["applied_labels"])

    def test_classify_messages_does_not_mark_promotions_with_order_words_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "eBay <shipping@ebay.com>",
                    "subject": "Top picks for your next order",
                    "snippet": "Save on collectibles this week.",
                    "body": "Best deals this week. Add to cart now. Unsubscribe anytime.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_PROMOTIONS"],
                    "list_unsubscribe": "<https://www.ebay.com/unsub>",
                    "precedence": "bulk",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])
        self.assertIn("promotions", review_queue["items"][0]["near_misses"])

    def test_classify_messages_keeps_requested_wishlist_sale_alerts_as_promotions(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Etsy <favorites@etsy.com>",
                    "subject": "A wishlist item just went on sale",
                    "snippet": "A saved item from your wishlist is now discounted.",
                    "body": "You asked to be notified when wishlist items drop in price.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_PROMOTIONS"],
                    "list_unsubscribe": "<https://www.etsy.com/unsub>",
                    "precedence": "bulk",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["promotions"])
        self.assertNotIn("spam-low-value", review_queue["items"][0]["applied_labels"])

    def test_classify_messages_marks_fake_payment_transaction_scam_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Powiadomienie Platnosci <notice@payment-alerts-example.com>",
                    "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                    "snippet": "Pilnie sprawdz szczegoly transakcji.",
                    "body": "Transakcja płatnicza oczekuje na potwierdzenie. Kliknij link aby zobaczyc szczegoly platnosci P24.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_job_application_updates_as_work(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Greenhouse <no-reply@greenhouse.io>",
                    "subject": "Update on your application",
                    "snippet": "Your interview has been scheduled.",
                    "body": "Thank you for applying. Your interview has been scheduled for next week.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["job-related"])

    def test_classify_messages_marks_linkedin_job_alerts_as_job_related(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
                    "subject": "GTM Engineer at FactFinder",
                    "snippet": "FactFinder GTM Engineer: Introduction",
                    "body": "LinkedIn Job Alerts. GTM Engineer at FactFinder. See job details and apply on LinkedIn.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": "<https://www.linkedin.com/unsub>",
                    "precedence": "bulk",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["job-related"])

    def test_classify_messages_marks_linkedin_saved_job_expiry_reminders_as_job_related(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "LinkedIn <jobs-noreply@linkedin.com>",
                    "subject": "Cezary, your saved job is expiring tomorrow! Product Manager at Example Corp",
                    "snippet": "Apply to your saved jobs.",
                    "body": "Your saved job is expiring tomorrow. Apply to your saved jobs on LinkedIn.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": "<https://www.linkedin.com/unsub>",
                    "precedence": "bulk",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["job-related"])

    def test_classify_messages_does_not_mark_class_action_notices_as_job_related_reply_needed(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Concilia <no-reply@conciliainc.com>",
                    "subject": "MGM Resorts International - Notice of a Class Action Settlement Approval Hearing",
                    "snippet": "Class action notice.",
                    "body": "This notice concerns a class action settlement approval hearing. Read the official notice for details.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertNotEqual(review_queue["items"][0]["applied_labels"], ["reply-needed", "job-related"])
        self.assertNotIn("job-related", review_queue["items"][0]["applied_labels"])

    def test_classify_messages_marks_german_amazon_order_updates_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Amazon.de <auto-confirm@amazon.de>",
                    "subject": "Ihre Amazon.de Bestellung wurde versandt",
                    "snippet": "Ihre Sendung ist unterwegs.",
                    "body": "Ihre Amazon.de Bestellung wurde versandt. Sendungsverfolgung ist jetzt verfugbar.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])

    def test_classify_messages_marks_google_play_receipts_as_shopping_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Google Play <googleplay-noreply@google.com>",
                    "subject": "Your Google Play Order Receipt from Apr 28, 2026",
                    "snippet": "Thank you. Your subscription continues and you've been charged.",
                    "body": "Google Play order receipt. Your subscription continues and you've been charged. Manage your subscriptions.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])

    def test_classify_messages_marks_wishlist_sale_reminders_as_promotions(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Steam <noreply@steampowered.com>",
                    "subject": "MEMORIAPOLIS from your Steam wishlist is now on sale!",
                    "snippet": "1 game you've wished for is on sale.",
                    "body": "A game from your wishlist is now on sale. Daily deal. Offer ends soon.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["promotions"])

    def test_classify_messages_marks_imf_publications_digest_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "IMF Publications News <publicationsnews@imf.org>",
                    "subject": "IMF Publications: April 2026 New and Noteworthy",
                    "snippet": "Global economics at your fingertips. Subscribe.",
                    "body": "IMF Publications newsletter. New and noteworthy releases. Subscribe for more publications.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": "<https://www.imf.org/unsub>",
                    "precedence": "bulk",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_open_house_reminders_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "The District Rental Apartments <noreply@thedistrictlangford.com>",
                    "subject": "Reminder: Open House This Saturday at The District",
                    "snippet": "There's more to this community than you might expect.",
                    "body": "Open house this Saturday. Tour the community and explore the amenities.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": "<https://www.thedistrictlangford.com/unsub>",
                    "precedence": "bulk",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_exact_trusted_personal_sender_as_personal(self) -> None:
        classifier = FixtureBatchClassifier(
            fixtures_dir=Path("."),
            trusted_personal_senders={"sophielyneriding@gmail.com"},
        )
        review_queue = classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Sophie Riding <sophielyneriding@gmail.com>",
                    "subject": "Trip photos",
                    "snippet": "A few pictures from the weekend.",
                    "body": "Sending over a few pictures from the weekend.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["personal"])

    def test_classify_messages_does_not_trust_same_display_name_from_different_address(self) -> None:
        classifier = FixtureBatchClassifier(
            fixtures_dir=Path("."),
            trusted_personal_senders={"sophielyneriding@gmail.com"},
        )
        review_queue = classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Sophie Riding <totally-different@example.com>",
                    "subject": "Trip photos",
                    "snippet": "A few pictures from the weekend.",
                    "body": "Sending over a few pictures from the weekend.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], [])


if __name__ == "__main__":
    unittest.main()
