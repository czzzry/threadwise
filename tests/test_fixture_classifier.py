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
                    "sender": '"Sophie Friend (via Google Drive)" <drive-shares-dm-noreply@google.com>',
                    "subject": 'Folder shared with you: "Bike trips 2026"',
                    "body": "Sophie Friend shared a folder with you in Google Drive.",
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
                    "subject": "Alex, your saved job is expiring tomorrow! Product Manager at Example Corp",
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

    def test_classify_messages_marks_linkedin_apply_now_job_recommendations_as_job_related(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "LinkedIn <jobs-noreply@linkedin.com>",
                    "subject": "Alex, apply now to ‘AI Product Manager at Quectel’",
                    "snippet": "Apply to your saved jobs.",
                    "body": "Apply to your saved jobs on LinkedIn and explore the role details.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": "<https://www.linkedin.com/unsub>",
                    "precedence": "bulk",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["job-related"])

    def test_classify_messages_marks_linkedin_apply_to_and_more_recommendations_as_job_related(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "LinkedIn <jobs-noreply@linkedin.com>",
                    "subject": "Alex, apply to Product Manager at Scrive and more",
                    "snippet": "Apply to Product Manager at Scrive and more.",
                    "body": "More roles recommended for you on LinkedIn. Apply to Product Manager at Scrive and more.",
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

    def test_classify_messages_marks_concilia_mgm_settlement_notice_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Concilia <no-reply@conciliainc.com>",
                    "subject": "MGM Resorts International – Notice of a Class Action Settlement Approval Hearing – Avis d'audience d'approbation de règlement",
                    "snippet": "Class action notice / Avis d'action collective",
                    "body": (
                        "This notice informs you of the settlement of the class action instituted against MGM Resorts "
                        "International. Class action notice / Avis d'action collective. You may opt out by May 17, 2026."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": "<https://sendy.conciliainc.com/unsubscribe/example>",
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

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

    def test_classify_messages_marks_amazon_shipped_updates_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "\"Amazon.de\" <versandbestaetigung@amazon.de>",
                    "subject": "Shipped: \"Backpacker's Journey...\" and 3 more items",
                    "snippet": "Your package was dispatched.",
                    "body": "Your package was dispatched. Ordered. Dispatched. Out for delivery. Delivered. Arriving tomorrow. Track package.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])

    def test_classify_messages_marks_real_shape_amazon_shipped_updates_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "\"Amazon.de\" <versandbestaetigung@amazon.de>",
                    "subject": "Shipped: \"Backpacker's Journey...\" and 3 more items",
                    "snippet": "Shipped: \"Backpacker's Journey...\" and 3 more items",
                    "body": "Your package was dispatched! Ordered Dispatched Out for delivery Delivered Arriving tomorrow Track package",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
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

    def test_classify_messages_marks_duolingo_password_exposure_notices_as_account_security(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Duolingo <no-reply@duolingo.com>",
                    "subject": "Take steps to secure your data",
                    "snippet": "We detected that your password has been exposed in a data breach on another platform while doing a routine check for your security.",
                    "body": "We detected that your password has been exposed in a data breach on another platform while doing a routine check for your security. You should reset your Duolingo password immediately, using a unique password not used elsewhere.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["account-security"])

    def test_classify_messages_marks_google_linked_services_reminders_as_account_security(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Google <google-noreply@google.com>",
                    "subject": "Reminder about linked Google services",
                    "snippet": "Update choices anytime in Google Account.",
                    "body": "Update choices anytime in Google Account. Reminder about linked Google services. Laws in the EU, including 5(2) of the Digital Markets Act, require Google to get consent to link these services.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["account-security"])

    def test_classify_messages_marks_trainline_delay_updates_as_travel(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Trainline <no-reply@comms.trainline.com>",
                    "subject": "Your train is delayed ⚠️",
                    "snippet": "Here's what you need to know.",
                    "body": "Your train is delayed. Here's what you need to know before you travel.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["travel"])

    def test_classify_messages_marks_trainline_trip_readiness_updates_as_travel(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Trainline <no-reply@comms.trainline.com>",
                    "subject": "Get ready for Nîmes Centre",
                    "snippet": "Don't forget to charge your phone.",
                    "body": "Get ready for your journey to Nîmes Centre. Don't forget to charge your phone before travel.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["travel"])

    def test_classify_messages_marks_real_shape_trainline_trip_readiness_updates_as_travel(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Trainline <no-reply@comms.trainline.com>",
                    "subject": "Get ready for Nîmes Centre",
                    "snippet": "Don't forget to charge your phone",
                    "body": "Don't forget to charge your phone. Trainline. Get ready to go. Your next trip, now with upgraded features. Your ticket.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["travel"])

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

    def test_classify_messages_marks_imf_legacy_data_shutdown_notice_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "IMF iData <idata@imf.org>",
                    "subject": "IMF Legacy Data Portal shutdown, September 28",
                    "snippet": "The IMF's legacy data portal will be decommissioned on September 28, 2025.",
                    "body": (
                        "As previously communicated, the IMF's legacy data portal will be decommissioned "
                        "on September 28, 2025. Use the new IMF Data Portal on data.imf.org."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
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

    def test_classify_messages_marks_young_mailroom_memo_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Young, Jenny" <clinic.contact@example.test>',
                    "subject": "GBGH Information: ED Team Mailboxes",
                    "snippet": "Hello ED team, Please note that your mailboxes have been all moved to the ED mailroom.",
                    "body": (
                        "Hello ED team. Please note that your mailboxes have been all moved to the ED mailroom, "
                        "and the folders in the physician lounge were removed. Switchboard will now place your mail upstairs only."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_PERSONAL"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_young_gynecological_services_memo_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Young, Jenny" <clinic.contact@example.test>',
                    "subject": "GBGH Memo - Temporary Pause of Gynecological Services - Dr. Agboola",
                    "snippet": "Sent on Behalf of Dr. Vik Ralhan, GBGH Chief of Staff",
                    "body": "Sent on behalf of Dr. Vik Ralhan, GBGH Chief of Staff.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_PERSONAL"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_linkedin_report_acknowledgements_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"LinkedIn Trust & Safety Team" <messages-noreply@linkedin.com>',
                    "subject": "We received your report",
                    "snippet": "Thank you for your report.",
                    "body": (
                        "We have received your report on a job post and are in the process of reviewing it. "
                        "You can view your report status page when we make a decision."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_inaturalist_event_nudges_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "iNaturalist Team <inaturalist@inaturalist.org>",
                    "subject": "Get outside this weekend!",
                    "snippet": "The City Nature Challenge starts April 24.",
                    "body": (
                        "This weekend, more than 100,000 people across 60+ countries will step outside and photograph "
                        "wild nature around them. It is the City Nature Challenge and we would love for you to join in."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": "<https://example.com/unsub>",
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_xai_api_announcements_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "xAI <noreply@x.ai>",
                    "subject": "Grok Build 0.1 now available via xAI API",
                    "snippet": "Our new coding model is now available via the xAI API.",
                    "body": "Dear API customers, our new coding model is now available via the xAI API.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_coursera_course_promos_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "University of Michigan <no-reply@m.mail.coursera.org>",
                    "subject": "Dive Deeper with Data Analysis",
                    "snippet": "Explore courses and series on the importance of digging into data.",
                    "body": (
                        "Data is the current currency of modern life. Explore courses and series on the importance "
                        "of digging into data and the insights and stories it can tell."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_PROMOTIONS"],
                    "list_unsubscribe": "<mailto:unsubscribe@mail.coursera.org>",
                    "precedence": "bulk",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_prime_video_subscription_end_notices_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Prime Video <no-reply@primevideo.com>",
                    "subject": "Deine Buchung von HBO Max Standard ist beendet",
                    "snippet": "Deine Buchung wurde vor Kurzem beendet.",
                    "body": (
                        "Deine Buchung von HBO Max Standard bei Prime Video wurde vor Kurzem beendet, "
                        "da du dich gegen eine automatische Verlängerung entschieden hast."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_knowledgehut_event_promos_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "upGrad KnowledgeHut <mailer@certs.knowledgehut.com>",
                    "subject": "Enter your name to confirm your seat",
                    "snippet": "Career Growth with ITIL - From Service Desk to Digital Operations Leader.",
                    "body": (
                        "Upcoming Event Career Growth with ITIL - From Service Desk to Digital Operations Leader. "
                        "Register here. You have received this because you have subscribed to receive emails "
                        "from upGrad KnowledgeHut."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": "<https://example.com/unsub>",
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_amazon_alexa_upgrade_notices_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Amazon Alexa <account-update@amazon.com>",
                    "subject": "You can now upgrade to Alexa+ for free",
                    "snippet": "Our smartest, most proactive AI assistant yet.",
                    "body": (
                        "Upgrade to the all-new Alexa. Alexa+ is included with Prime on your device. "
                        "Get access to the full Alexa+ experience when you join Prime."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_prime_membership_resume_notices_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Amazon Prime <prime@amazon.com>",
                    "subject": "Welcome back to Prime!",
                    "snippet": "Your Prime membership resumes today.",
                    "body": (
                        "Welcome back. Plan name Prime. Plan type Monthly $14.99 plus tax. "
                        "Renewal date April 29, 2026. You've resumed your membership."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_youtube_premium_welcome_notices_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "YouTube <noreply-purchases@youtube.com>",
                    "subject": "Welcome to Premium Lite",
                    "snippet": "Your payment method will be charged monthly starting on Apr 30, 2026.",
                    "body": (
                        "Hi Alex, welcome to Premium Lite on YouTube. Your payment method will be charged "
                        "monthly starting on Apr 30, 2026. You can manage and cancel your membership any time."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_instaffo_job_reengagement_promos_as_work(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Instaffo <notifications@app.instaffo.com>",
                    "subject": "Jobs mit top Gehältern und Remote Option entdecken 😍",
                    "snippet": "Warum du deine Registrierung bei Instaffo abschließen solltest.",
                    "body": (
                        "Hier sind 5 überzeugende Gründe, warum du deine Registrierung bei Instaffo abschließen "
                        "solltest. Du erhältst ausschließlich Jobvorschläge, die perfekt zu dir passen."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["job-related"])

    def test_classify_messages_marks_google_home_gemini_rollout_notices_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Google Home <googlehome@google.com>",
                    "subject": "Get started with Gemini for Home voice assistant",
                    "snippet": "You now have access to the Gemini for Home voice assistant.",
                    "body": (
                        "Say hello to Gemini. You now have access to the Gemini for Home voice assistant at Home. "
                        "Explore next-level smart home features and click below to learn how to get started."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_audible_order_confirmations_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Audible.com" <donotreply@audible.com>',
                    "subject": "Your order is confirmed",
                    "snippet": "Here's your order confirmation.",
                    "body": (
                        "Welcome to Audible. Here's your order confirmation. "
                        "Order number D01-6116019-5939444 Apple In-App Purchase."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_paypal_legal_agreement_updates_as_finance(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "PayPal Communications <no_reply@communications.paypal.com>",
                    "subject": "We're making some changes to our PayPal legal agreements",
                    "snippet": "We are making some changes to our legal agreements.",
                    "body": "We are making some changes to our PayPal legal agreements.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["financial-account"])

    def test_classify_messages_marks_sun_life_survey_nudges_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Sun Life <sunlife@email.sunlife.com>",
                    "subject": "Share your Sun Life experience with us",
                    "snippet": "Please share your feedback to help us improve your experience.",
                    "body": (
                        "Please share your feedback to help us improve your experience as a Sun Life Choices "
                        "Client. Complete the survey for a chance to win one of five $200 e-gift cards."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_google_play_subscription_end_notices_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Google Play <googleplay-noreply@google.com>",
                    "subject": "Your YouTube subscription benefits are ending soon",
                    "snippet": "Your YouTube Premium subscription will end soon.",
                    "body": (
                        "Your YouTube Premium subscription will end on 6 Dec. After that, you'll lose access "
                        "to subscription benefits. Resubscribe."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_talkpal_receipts_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"TalkPal, Inc." <invoice+statements@talkpal.ai>',
                    "subject": "Your receipt from TalkPal, Inc. #2197-6006",
                    "snippet": "Receipt from TalkPal, Inc. €89.99 Paid November 29, 2025.",
                    "body": (
                        "Receipt from TalkPal, Inc. €89.99 Paid November 29, 2025. Receipt number 2197-6006. "
                        "Invoice number W6PLMYSJ-0002. Talkpal Premium Qty 1."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_eversports_purchase_notices_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Yoga Barn Berlin namaste@yoga-barn-berlin.de via Eversports" <no-reply@eversports.com>',
                    "subject": "Dein Kauf bei Yoga Barn Berlin",
                    "snippet": "Danke für den Einkauf bei Yoga Barn Berlin.",
                    "body": (
                        "Hi Alex, danke für den Einkauf bei Yoga Barn Berlin. "
                        "Die Rechnung findest du im Anhang."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_eversports_booking_notices_as_calendar_events(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Yoga Barn Berlin namaste@yoga-barn-berlin.de via Eversports" <no-reply@eversports.com>',
                    "subject": "Deine Anmeldung bei Yoga Barn Berlin",
                    "snippet": "Hier findest du nochmal alle Informationen zusammengefasst.",
                    "body": (
                        "Deine Anmeldung. Hier findest du nochmal alle Informationen zusammengefasst. "
                        "Yin Yoga & Yoga Nidra. Reserviert am 28.11.2025 18:33 Uhr. "
                        "Datum 28.11.2025 20:15 - 21:30 Uhr."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["calendar-event"])

    def test_classify_messages_marks_requested_youtube_premiere_reminders_as_promotions(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "YouTube <noreply@youtube.com>",
                    "subject": "Rufo & Lomez just started a Premiere",
                    "snippet": "You requested a reminder for this event.",
                    "body": (
                        "Rufo & Lomez just started a Premiere. You received this email because you requested "
                        "a reminder for this event. You will only receive reminders for the events you select."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["promotions"])

    def test_classify_messages_marks_trello_account_deletion_notices_as_account_security(self) -> None:
        cases = [
            {
                "sender": "Trello <do-not-reply@trello.com>",
                "subject": "Final notice: Your Trello account will be deleted",
                "snippet": "Log in to Trello before November 25, 2025.",
                "body": (
                    "Log in to Trello before November 25, 2025 to keep your account active. "
                    "Otherwise, your Trello data will be deleted."
                ),
            },
            {
                "sender": "Trello <do-not-reply@trello.com>",
                "subject": "Action required: Jump back into Trello to keep your account",
                "snippet": "Log in to Trello before November 11, 2025.",
                "body": (
                    "Log in to Trello before November 11, 2025 to keep your account active. "
                    "Otherwise, your Trello data will be deleted."
                ),
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        for item in review_queue["items"]:
            with self.subTest(subject=item["subject"]):
                self.assertEqual(item["applied_labels"], ["account-security"])

    def test_classify_messages_marks_komoot_weekend_suggestions_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Komoot <noreply@komoot.de>",
                    "subject": "This Weekend: Victory Column, Nature Reserve, or Volkspark Rehberge",
                    "snippet": "These Highlights will make your weekend.",
                    "body": (
                        "These Highlights will make your weekend. Here are three must-see spots to inspire "
                        "your next activity. We picked them just for you."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_prime_video_channel_end_notices_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Prime Video <no-reply@primevideo.com>",
                    "subject": "Deine Buchung von CNMA Arthouse ist beendet",
                    "snippet": "Deine Buchung wurde vor Kurzem beendet.",
                    "body": (
                        "Deine Buchung von CNMA Arthouse bei Prime Video wurde vor Kurzem beendet, "
                        "da du dich gegen eine automatische Verlängerung entschieden hast."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_audible_new_title_promos_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Audible.de" <noreply@audible.de>',
                    "subject": "Neuer Titel von Christopher Clark!",
                    "snippet": "Entdecke den brandneuen Titel von Christopher Clark.",
                    "body": (
                        "Entdecke den brandneuen Titel von Christopher Clark. "
                        "Jetzt hören. Titel, die du nicht verpassen willst."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_amazon_return_flow_messages_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"rueckgabe@amazon.de" <rueckgabe@amazon.de>',
                    "subject": "Your refund for Example Item",
                    "snippet": "Your refund was issued.",
                    "body": (
                        "Your refund was issued. View refund summary. Return summary. "
                        "Total refund. Amazon account balance."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_uber_trip_receipts_as_receipts(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Uber Receipts <noreply@uber.com>",
                    "subject": "Your Wednesday evening trip with Uber",
                    "snippet": "Thanks for riding, here is your trip receipt.",
                    "body": (
                        "Thanks for riding. Trip receipt. Fare breakdown. View trip details. "
                        "Receipt available in your account."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["receipt-billing"])

    def test_classify_messages_marks_dhl_shipment_updates_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "DHL Paket <noreply@dhl.de>",
                    "subject": "Ihre Amazon Sendung kommt heute",
                    "snippet": "Ihre Sendung wird zugestellt.",
                    "body": (
                        "Ihre Sendung wird zugestellt. Amazon Sendung kommt heute. "
                        "Sendung wird verladen."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_restaurant_reservation_messages_as_calendar_events(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "La Piccola Perla <noreply@choiceqr.com>",
                    "subject": "Reservation reminder",
                    "snippet": "Your reservation was accepted.",
                    "body": (
                        "Your reservation was accepted. Reminder reservation 18:00 5 guests. "
                        "Add to calendar. Reservation request sent."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["calendar-event"])

    def test_classify_messages_marks_prime_billing_problem_notices_as_account_security(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Amazon Prime <prime@amazon.com>",
                    "subject": "Your Prime benefits are on hold due to a billing issue",
                    "snippet": "We are unable to charge your payment method.",
                    "body": (
                        "We are unable to charge your payment method. Your Prime membership has been paused. "
                        "Update your payment method to restore access."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["account-security"])

    def test_classify_messages_marks_meetup_account_deactivation_notices_as_account_security(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Meetup <info@email.meetup.com>",
                    "subject": "Your Meetup account will be deactivated",
                    "snippet": "Log in to keep your Meetup account active.",
                    "body": (
                        "Your Meetup account will be deactivated unless you log in. "
                        "Your data will be scheduled for deletion."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["account-security"])

    def test_classify_messages_marks_peoplenet_application_updates_as_job_related(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Peoplenet Notifications <peoplenet@bertelsmann-hr.de>",
                    "subject": "Eingangsbestätigung Bewerbung",
                    "snippet": "Deine Bewerbung ist eingegangen.",
                    "body": (
                        "Deine Bewerbung für die Position ist bei uns eingegangen. "
                        "Vielen Dank dafür. Personalabteilung wird sich melden."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["job-related"])

    def test_classify_messages_marks_x_login_alerts_as_account_security(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "X <verify@x.com>",
                    "subject": "New login to X from ChromeDesktop on Mac",
                    "snippet": "We noticed a login to your account from a new device.",
                    "body": (
                        "We noticed a login to your account from a new device. Was this you? "
                        "New login location Berlin, Germany."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["account-security"])

    def test_classify_messages_marks_slack_email_confirmation_as_account_security(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Slack <no-reply-eG0SxztHaBWx5NIIHphUrjXB@slack.com>",
                    "subject": "Confirm your email address on Slack",
                    "snippet": "Confirm your email address to get started on Slack.",
                    "body": (
                        "Confirm your email address to get started on Slack. "
                        "If you didn't request this email, there's nothing to worry about."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["account-security"])

    def test_classify_messages_marks_ebay_new_device_notice_as_account_security(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "eBay <ebay@ebay.com>",
                    "subject": "Ihr Konto wird mit einem neuen Gerät genutzt",
                    "snippet": "Ihr Konto wird mit einem neuen Gerät genutzt.",
                    "body": (
                        "Ihr Konto wird mit einem neuen Gerät genutzt. "
                        "Wenn Sie das nicht waren, überprüfen Sie bitte Ihre Kontosicherheit."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["account-security"])

    def test_classify_messages_marks_xai_deprecation_announcements_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "xAI <noreply@x.ai>",
                    "subject": "xAI Messages API Endpoint Deprecation",
                    "snippet": "API endpoint deprecation notice.",
                    "body": "Messages API endpoint deprecation notice for xAI customers.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_amazon_item_cancellation_updates_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Amazon.de" <order-update@amazon.de>',
                    "subject": "Item cancelled successfully",
                    "snippet": "Your order was cancelled.",
                    "body": "Your items were cancelled. Your order was cancelled. You have not been charged.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_amazon_seller_messages_with_order_context_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "no-reply <no-reply@amazon.de>",
                    "subject": "Versicherungsunterlagen",
                    "snippet": "You have received a message from the Amazon Seller.",
                    "body": (
                        "You have received a message from the Amazon Seller. Order ID 302-1498468-9117102. "
                        "Assurant Europe Insurance documents."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_paypal_contact_change_notices_as_account_security(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"service@intl.paypal.com" <service@intl.paypal.com>',
                    "subject": "You added your phone number to your account",
                    "snippet": "You added your phone number to your account.",
                    "body": "You added your phone number to your account.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["account-security"])

    def test_classify_messages_marks_coursera_marketing_roundups_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "University of Michigan <no-reply@m.mail.coursera.org>",
                    "subject": "Thinking Clearly in an AI-Driven World",
                    "snippet": "We have collected courses to help you.",
                    "body": (
                        "We have collected courses to help you focus on what matters the most. "
                        "This month Michigan Online is highlighting the tools you need."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_przelewy24_transaction_notices_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Przelewy24.pl" <no-reply@przelewy24.pl>',
                    "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                    "snippet": "Informacja o transakcji P24-Y6A-Y4M-T1W.",
                    "body": (
                        "Informujemy o zarejestrowaniu nowej transakcji płatniczej w Serwisie Przelewy24 "
                        "dla INPOST SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_prime_video_channel_lifecycle_variants_as_orders(self) -> None:
        cases = [
            {
                "sender": "Amazon Prime Video <no-reply@primevideo.com>",
                "subject": "Confirmation - Your special offer on your AXN White subscription",
                "snippet": "You have taken advantage of a special offer by continuing your subscription.",
                "body": (
                    "You have taken advantage of a special offer by continuing your AXN White subscription "
                    "on Prime Video. Starting with your next renewal, your payment method on file will be charged."
                ),
            },
            {
                "sender": "Prime Video <no-reply@primevideo.com>",
                "subject": "Du hast AXN White bei Prime Video gebucht",
                "snippet": "Details zu deiner Zusatzkanal-Buchung.",
                "body": (
                    "Du hast kuerzlich Gratiszeitraum-Angebot fuer AXN White auf Prime Video gestartet. "
                    "Diese E-Mail enthaelt eine Uebersicht deiner Zusatzkanal-Details."
                ),
            },
            {
                "sender": "Prime Video <no-reply@primevideo.com>",
                "subject": "Kundigung deiner Buchung von BATTLEZONE",
                "snippet": "Wie gewuenscht haben wir deine Buchung gekuendigt.",
                "body": (
                    "Wie gewuenscht haben wir deine Buchung von BATTLEZONE bei Prime Video gekuendigt. "
                    "Du erhaeltst eine Rueckerstattung."
                ),
            },
            {
                "sender": "Prime Video <no-reply@primevideo.com>",
                "subject": "Aenderung an deiner Buchung von FILMLEGENDEN",
                "snippet": "Du hast dich von der automatischen Verlaengerung abgemeldet.",
                "body": (
                    "Du hast dich fuer FILMLEGENDEN bei Prime Video von der automatischen Verlaengerung "
                    "abgemeldet. Dein Zugriff auf diesen Zusatzkanal endet spaeter."
                ),
            },
            {
                "sender": "Prime Video <no-reply@primevideo.com>",
                "subject": "Du hast Paramount+ Standard bei Prime Video gebucht",
                "snippet": "Details zu deiner Zusatzkanal-Buchung.",
                "body": (
                    "Du hast kuerzlich Gratiszeitraum-Angebot fuer Paramount+ Standard auf Prime Video gestartet. "
                    "Diese E-Mail enthaelt eine Uebersicht deiner Zusatzkanal-Details."
                ),
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        for item in review_queue["items"]:
            with self.subTest(subject=item["subject"]):
                self.assertEqual(item["applied_labels"], ["shopping-order"])
                self.assertIn("receipt-billing", item["near_misses"])

    def test_classify_messages_marks_subscription_state_messages_as_orders(self) -> None:
        cases = [
            {
                "sender": "no-reply@amazon.com",
                "subject": "Amazon.com subscription at risk of cancelation",
                "snippet": "We were unable to process the payment for your subscription order.",
                "body": (
                    "We were unable to process the payment with the payment method that you selected "
                    "for your Amazon.com subscription order D01-6618536-7120255."
                ),
            },
            {
                "sender": "Audible Customer Service <do-not-reply@audible.com>",
                "subject": "We're sorry to see you go",
                "snippet": "We're confirming that your Audible membership was cancelled.",
                "body": (
                    "We're confirming that your Audible membership was cancelled and you no longer "
                    "have access to member benefits."
                ),
            },
            {
                "sender": '"Audible.com" <do_not_reply@audible.com>',
                "subject": "You've cancelled your membership",
                "snippet": "Your Audible membership will be cancelled soon.",
                "body": (
                    "Your Audible membership will be cancelled on February 4, 2026. "
                    "You will continue to have access before this date."
                ),
            },
            {
                "sender": '"Audible.com" <do-not-reply@audible.com>',
                "subject": "Reminder: Your Audible trial is ending soon",
                "snippet": "Your free trial ends soon and you will be charged.",
                "body": (
                    "Your Audible Premium Plus free trial ends soon, at which point "
                    "you'll be charged for the first time unless you cancel."
                ),
            },
            {
                "sender": "LinkedIn <billing-noreply@linkedin.com>",
                "subject": "You have canceled Premium Career",
                "snippet": "Your subscription has been canceled.",
                "body": (
                    "Your subscription of Premium Career has been canceled. "
                    "You will continue to have access until a later date."
                ),
            },
            {
                "sender": "YouTube <noreply-purchases@youtube.com>",
                "subject": "Welcome to YouTube Premium",
                "snippet": "Welcome to your YouTube Premium membership.",
                "body": (
                    "Welcome to your YouTube Premium membership. "
                    "You can manage and cancel your membership any time. Order number included."
                ),
            },
            {
                "sender": '"Amazon.de" <order-update@amazon.de>',
                "subject": 'Item cancelled successfully: "Wessper Water Filter Jug..."',
                "snippet": "Your order was cancelled.",
                "body": (
                    "Your order was cancelled. You have not been charged for this order. "
                    "View your orders for more details."
                ),
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        for item in review_queue["items"]:
            with self.subTest(subject=item["subject"]):
                self.assertEqual(item["applied_labels"], ["shopping-order"])
                self.assertIn("receipt-billing", item["near_misses"])

    def test_classify_messages_marks_amazon_payment_declined_order_notices_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Amazon.de" <payments-update@amazon.de>',
                    "subject": "Your Payment has been declined",
                    "snippet": "Unfortunately, the payment for this order has failed.",
                    "body": (
                        "Unfortunately, the payment for this order has failed. "
                        "In order to proceed with your order and avoid cancellation, "
                        "please update the payment method within 5 days."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_low_value_backlog_families_as_low_value(self) -> None:
        cases = [
            {
                "sender": "iNaturalist Team <inaturalist@inaturalist.org>",
                "subject": "iNaturalist turns 18 - come celebrate with us!",
                "snippet": "Share your photos of local species.",
                "body": (
                    "iNaturalist is turning 18. Join the birthday project and share your photos of local species."
                ),
            },
            {
                "sender": "Project Management Institute <email@mail.pmi.org>",
                "subject": "Rethink Success: Achieve MORE with Denis Lassance",
                "snippet": "Join this thought-leadership session.",
                "body": (
                    "Register for this event and rethink success with Denis Lassance. "
                    "Achieve more with this Project Management Institute session."
                ),
            },
            {
                "sender": "OpenAI <noreply@email.openai.com>",
                "subject": "Updates to OpenAI's Privacy Policy",
                "snippet": "We're updating our privacy policy.",
                "body": (
                    "We wanted to let you know that we're updating our Privacy Policy to give you more information "
                    "about what data we collect and how we use it."
                ),
            },
            {
                "sender": "Amazon Answers <answers@amazon.de>",
                "subject": "Your question on Amazon did not receive any answers",
                "snippet": "Your question is unlikely to receive an answer.",
                "body": (
                    "Unfortunately none of them have yet responded. At this point your question is unlikely "
                    "to receive an answer."
                ),
            },
            {
                "sender": "LinkedIn <updates-noreply@linkedin.com>",
                "subject": "Kate Minnema and others share their thoughts on LinkedIn",
                "snippet": "Kate Minnema shared a post.",
                "body": (
                    "Kate Minnema shared a post. Charles University shared a post. "
                    "Others share their thoughts on LinkedIn."
                ),
            },
            {
                "sender": '"GOG.COM" <notice-noreply@email3.gog.com>',
                "subject": "We are updating GOG terms",
                "snippet": "Please review our updated terms.",
                "body": "We are updating GOG terms and this notice explains the changes.",
            },
            {
                "sender": "Subscription Membership Settlement <SubscriptionMembershipSettlement@admin.kccllc.com>",
                "subject": "Re: cheque re-issue not working",
                "snippet": "Please use our check reissue portal.",
                "body": (
                    "If you received a settlement check or electronic payment that you are unable to redeem, "
                    "please go to our check reissue portal."
                ),
            },
            {
                "sender": "Purple <no-reply@purple.ai>",
                "subject": "Your wifi plan - upgrade",
                "snippet": "Thanks for activating your free wifi plan.",
                "body": (
                    "Thanks for activating your free wifi plan at MAN T1 Departures. "
                    "Here's a quick email to confirm your plan."
                ),
            },
            {
                "sender": "Sporcle <do-not-reply@sporcle.com>",
                "subject": "You Earned a New Trophy",
                "snippet": "You earned a new trophy.",
                "body": "Nice work. You earned a new trophy: 1 Year Club.",
            },
            {
                "sender": "University of Michigan <no-reply@m.mail.coursera.org>",
                "subject": "Thinking Clearly in an AI-Driven World",
                "snippet": "Critical thinking and data literacy courses.",
                "body": (
                    "Critical thinking, data literacy, and thoughtful use of AI can help you. "
                    "Explore these University of Michigan learning opportunities."
                ),
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": "<https://example.com/unsub>",
                    "precedence": "bulk",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        for item in review_queue["items"]:
            with self.subTest(subject=item["subject"]):
                self.assertEqual(item["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_finance_and_reservation_backlog_families(self) -> None:
        cases = [
            {
                "sender": "Peoplenet Notifications <peoplenet@bertelsmann-hr.de>",
                "subject": "Willkommen zur Talent Community von Bertelsmann und seinen Divisionen",
                "snippet": "Dein Account wurde erfolgreich erstellt.",
                "body": (
                    "Wir freuen uns sehr ueber deine Anmeldung in unserem Karriereportal. "
                    "Dein Account wurde erfolgreich erstellt."
                ),
                "expected_labels": ["job-related"],
            },
            {
                "sender": "Wise <noreply@wise.com>",
                "subject": "We're updating our Privacy Notices",
                "snippet": "We're updating our privacy notices.",
                "body": "We're updating our Privacy Notices for your Wise account.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "notification@paypal.com",
                "subject": "You've added a new email address to your PayPal account",
                "snippet": "You've added a new email address.",
                "body": "You've added a new email address to your PayPal account.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Sun Life <sunlife@info.sunlife.ca>",
                "subject": "Your RRSP contribution limit has reset with Sun Life",
                "snippet": "Review your annual contribution limit.",
                "body": (
                    "The contribution limit for your Group Choices Plan RRSP has reset. "
                    "Review your annual limit before starting contributions."
                ),
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "Kasa Stefczyka <kasastefczyka@stefczykonline.pl>",
                "subject": "Arkusz informacyjny dla deponentow",
                "snippet": "Informacyjny dla deponentow.",
                "body": "Arkusz informacyjny dla deponentow i informacje o rachunku.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "Reserve with Google <reserve-noreply@google.com>",
                "subject": "Your reservation at La Piccola Perla is confirmed",
                "snippet": "Add to Google Calendar.",
                "body": (
                    "Your class is booked. Booking 6:00 PM. Add to Google Calendar. "
                    "View reservation and get directions."
                ),
                "expected_labels": ["calendar-event"],
            },
            {
                "sender": '"PID Litacka" <robot@operatorict.cz>',
                "subject": "Registration",
                "snippet": "Use the following link to activate your user account.",
                "body": (
                    "Please use the following link to activate your user account. "
                    "We wish you pleasant travelling by Prague Integrated Transport."
                ),
                "expected_labels": ["travel"],
            },
            {
                "sender": "Wealthsimple <notifications@o.wealthsimple.com>",
                "subject": "We've updated your account agreement",
                "snippet": "We've made changes to your client account agreement.",
                "body": (
                    "We've made some changes to your Client Account Agreement with Wealthsimple Investments Inc."
                ),
                "expected_labels": ["financial-account"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_real_backlog_variants_without_bulk_headers(self) -> None:
        cases = [
            {
                "sender": "noreply@td.com",
                "subject": "Use extra caution - phishing scams",
                "snippet": "TD Direct Investing",
                "body": "TD Direct Investing. Use extra caution - phishing scams.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "OpenAI <noreply@email.openai.com>",
                "subject": "Updates to OpenAI's Privacy Policy",
                "snippet": "We're updating our privacy policy.",
                "body": (
                    "We wanted to let you know that we're updating our Privacy Policy to give you even more "
                    "information about what data we collect and how we use it."
                ),
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": '"GOG.COM" <notice-noreply@email3.gog.com>',
                "subject": "We are updating GOG terms",
                "snippet": "Plain text version not available",
                "body": "Plain text version not available",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "LinkedIn <updates-noreply@linkedin.com>",
                "subject": "Kate Minnema and others share their thoughts on LinkedIn",
                "snippet": "Kate Minnema shared a post.",
                "body": (
                    "Kate Minnema shared a post. Charles University shared a post. "
                    "Others share their thoughts on LinkedIn."
                ),
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": '"Amazon.de" <order-update@amazon.de>',
                "subject": 'Item cancelled successfully: "Wessper Water Filter Jug..."',
                "snippet": "Your order was cancelled.",
                "body": (
                    "Your order was cancelled. You have not been charged for this order. "
                    "View your orders."
                ),
                "expected_labels": ["shopping-order"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_audible_discount_promos_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": '"Audible.de" <noreply@audible.de>',
                    "subject": "Dieser 50% Rabatt ist nur fuer dich.",
                    "snippet": "50% Rabatt ist nur fuer dich.",
                    "body": "Dieser 50% Rabatt ist nur fuer dich. Jetzt hoeren mit Audible.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_inaturalist_advocacy_nudges_as_low_value(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "iNaturalist Team <inaturalist@inaturalist.org>",
                    "subject": "How you can make a difference for nature",
                    "snippet": "Make a difference for nature.",
                    "body": "How you can make a difference for nature and support biodiversity with iNaturalist.",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_meinlieblingsrahmen_shipment_updates_as_orders(self) -> None:
        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Mein Lieblingsrahmen <info@meinlieblingsrahmen.de>",
                    "subject": "Deine Bestellung bei Mein Lieblingsrahmen wurde versendet",
                    "snippet": "Deine Bestellung wurde versendet.",
                    "body": (
                        "Hallo Alex, der Lieferstatus fuer deine Bestellung bei Mein Lieblingsrahmen hat sich "
                        "geaendert. Die Bestellung hat jetzt den Lieferstatus: Versandt."
                    ),
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                }
            ],
        )

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["shopping-order"])
        self.assertIn("receipt-billing", review_queue["items"][0]["near_misses"])

    def test_classify_messages_marks_batch_31_order_and_receipt_variants(self) -> None:
        cases = [
            {
                "sender": "PayPal <service@intl.paypal.com>",
                "subject": "Receipt for Your Payment to effect Bilderrahmen...",
                "snippet": "Receipt for your payment.",
                "body": "Receipt for Your Payment to effect Bilderrahmen. Transaction details and receipt.",
                "expected_labels": ["receipt-billing"],
            },
            {
                "sender": "Mein Lieblingsrahmen <info@meinlieblingsrahmen.de>",
                "subject": "Deine Bestellung bei Mein Lieblingsrahmen wurde komplett bezahlt",
                "snippet": "Wir haben deine Zahlung erhalten.",
                "body": (
                    "Wir haben deine Zahlung erhalten und werden die Bestellung nun weiter verarbeiten. "
                    "Bestellnummer: 64369."
                ),
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Mein Lieblingsrahmen <info@meinlieblingsrahmen.de>",
                "subject": "Bestellbestätigung",
                "snippet": "Vielen Dank fuer deine Bestellung.",
                "body": "Vielen Dank fuer deine Bestellung. Bestellnummer: 64369. Gesamtbetrag 89,26 EUR.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Talkpal - AI German Teacher <hello@talkpal.ai>",
                "subject": "Your premium subscription is now active",
                "snippet": "You just unlocked all the modes.",
                "body": "Your premium subscription is now active. You just unlocked all the modes and AI features.",
                "expected_labels": ["shopping-order"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_31_account_security_variants(self) -> None:
        cases = [
            {
                "sender": '"service@intl.paypal.com" <service@intl.paypal.com>',
                "subject": "Stay logged in on this trusted device",
                "snippet": "Stay logged in on this trusted device.",
                "body": "Stay logged in on this trusted device for future PayPal sign-ins.",
            },
            {
                "sender": "Ubisoft Account Updates <updates@account.ubisoft.com>",
                "subject": "Ubisoft Account Security Code",
                "snippet": "Temporary security code.",
                "body": "Here is a temporary security code for your Ubisoft Account. It can only be used once.",
            },
            {
                "sender": "LinkedIn <security-noreply@linkedin.com>",
                "subject": "Alex, a new email address was added to your account",
                "snippet": "A new email address was added.",
                "body": "The email address founder-proton@example.test was recently added to your LinkedIn account.",
            },
            {
                "sender": "LinkedIn <security-noreply@linkedin.com>",
                "subject": "Alex, here's your PIN 349599",
                "snippet": "Enter this 6-digit code.",
                "body": "Enter this 6-digit code to verify it's you. We recommend changing your password if you did not request it.",
            },
            {
                "sender": "Kinguin <legal@notices.kinguin.net>",
                "subject": "Important update: Inactive Accounts Policy at Kinguin and Your Account Status",
                "snippet": "Inactive accounts may be frozen.",
                "body": (
                    "Inactive accounts may be frozen or deactivated to protect your data. "
                    "Please make a transaction or contact customer support."
                ),
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        for item in review_queue["items"]:
            with self.subTest(subject=item["subject"]):
                self.assertEqual(item["applied_labels"], ["account-security"])

    def test_classify_messages_marks_batch_31_low_value_invites(self) -> None:
        cases = [
            {
                "sender": "iNaturalist Team <inaturalist@inaturalist.org>",
                "subject": "You're invited to a live iNaturalist event!",
                "snippet": "Webinar on Identifying and How You Can Help.",
                "body": (
                    "Join us on Thursday to learn more about how you can help others identify observations. "
                    "Please register if you want the recording."
                ),
            }
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        for item in review_queue["items"]:
            self.assertEqual(item["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_batch_32_follow_on_families(self) -> None:
        cases = [
            {
                "sender": "LinkedIn <billing-noreply@linkedin.com>",
                "subject": "Thank you for purchasing Premium Career",
                "snippet": "Your purchase is confirmed.",
                "body": "Thank you for purchasing Premium Career. Your subscription is now active and your receipt is attached.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "info@imploy.co",
                "subject": "Welcome to Imploy! Let's Get Started.",
                "snippet": "Welcome to Imploy.",
                "body": "Welcome to Imploy! Let's get started with your recruiting profile.",
                "expected_labels": ["job-related"],
            },
            {
                "sender": "eBay - qwerty-nelis <amster_drsl5797mh@members.ebay.de>",
                "subject": "Betreff: cez_7932 hat eine Nachricht gesendet zu Olive Green Typewriter",
                "snippet": "Eine Nachricht wurde gesendet.",
                "body": "cez_7932 hat eine Nachricht gesendet zu deinem eBay Artikel. Bitte antworte im eBay Nachrichten-Center.",
                "expected_labels": ["reply-needed", "shopping-order"],
            },
            {
                "sender": '"rueckgabe@amazon.de" <rueckgabe@amazon.de>',
                "subject": "You've been charged for Salomon Trailblazer 20 Backpack....",
                "snippet": "Your original payment method has been charged.",
                "body": (
                    "Your original payment method has been charged because we have not received the original item yet. "
                    "View your return."
                ),
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Google <google-noreply@google.com>",
                "subject": "Your Gmail will stop working in 5 days",
                "snippet": "You're out of storage.",
                "body": "You've used all 15 GB of your Google Account storage. Send and receive emails on Gmail will stop.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "TD <noreply@td.com>",
                "subject": "TD Reminder: Canada Post disruption",
                "snippet": "Canada Post disruption reminder.",
                "body": "TD Reminder: Canada Post disruption. Important account servicing information.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "Sun Life <sunlife@info.sunlife.ca>",
                "subject": "Stay protected with Sun Life's new Cybersecurity Hub!",
                "snippet": "Visit the hub today.",
                "body": "We're proud to share our newly updated Cybersecurity Hub. Explore the hub and stay safe online.",
                "expected_labels": ["spam-low-value"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_33_follow_on_families(self) -> None:
        cases = [
            {
                "sender": "eBay <ebay@ebay.com>",
                "subject": "cez_7932, Sie koennen immer noch eine Bewertung abgeben",
                "snippet": "Bewertung abgeben.",
                "body": "Sie koennen immer noch eine Bewertung abgeben fuer Ihren letzten Kauf.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "eBay <ebay@ebay.com>",
                "subject": "cez_7932, bitte bewerten Sie Ihren letzten Kauf",
                "snippet": "Bitte bewerten Sie Ihren letzten Kauf.",
                "body": "Bitte bewerten Sie Ihren letzten Kauf auf eBay.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "eBay - whiskerwondersshop <ptahja_grib4226rf@members.ebay.com>",
                "subject": "whiskerwondersshop hat eine Frage zu Artikelnr. 335644951493 gesendet",
                "snippet": "Eine Frage zu Ihrem Artikel.",
                "body": "whiskerwondersshop hat eine Frage zu Ihrem Artikel gesendet. Bitte antworten Sie im eBay Nachrichten-Center.",
                "expected_labels": ["reply-needed", "shopping-order"],
            },
            {
                "sender": '"donotreply@fedex.com" <noreply@fedex.com>',
                "subject": "Ihre Sendung wurde geliefert. 884653092668",
                "snippet": "Ihre Sendung wurde geliefert.",
                "body": "Ihre Sendung wurde geliefert.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Hermes Zustellbenachrichtigung <noreply@paketankuendigung.myhermes.de>",
                "subject": "Dein Hermes Paket von FedEx Express Deutschland GmbH liegt bei deinem Nachbarn.",
                "snippet": "Paket liegt beim Nachbarn.",
                "body": "Dein Hermes Paket liegt bei deinem Nachbarn.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "eBay <ebay@ebay.com>",
                "subject": "IN ZUSTELLUNG: KYOCERA 902KC DIGNO ...",
                "snippet": "In Zustellung.",
                "body": "IN ZUSTELLUNG fuer Ihren eBay Kauf.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": '"Hermes Paketankuendigung" <noreply@paketankuendigung.myhermes.de>',
                "subject": "Deine Hermes Sendung von FedEx Express Deutschland GmbH ist auf dem Weg",
                "snippet": "Sendung ist auf dem Weg.",
                "body": "Deine Hermes Sendung ist auf dem Weg.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "eBay <ebay@ebay.com>",
                "subject": "Kuerzlich angesehen: FREETEL MODE 1 RETRO II 2",
                "snippet": "Kuerzlich angesehen.",
                "body": "Kuerzlich angesehen auf eBay.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Cloud4wi <noreply@cloud4wi.com>",
                "subject": "Northern Wi-Fi, validate your email address",
                "snippet": "Validate your email address.",
                "body": "Validate your email address to continue using Northern Wi-Fi.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "noreply@td.com",
                "subject": "Canada Post service disruption will cause mail delivery delays",
                "snippet": "Mail delivery delays.",
                "body": "Canada Post service disruption will cause mail delivery delays for TD mail.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": '"donotreply@fedex.com" <noreply@fedex.com>',
                "subject": "Ihr Paket wird von unserem lokalen Anbieter geliefert: Hermes",
                "snippet": "Lokaler Anbieter liefert.",
                "body": "Ihr Paket wird von unserem lokalen Anbieter geliefert: Hermes.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "eBay <ebay@ebay.com>",
                "subject": "Ihre Sendung ist jetzt bei SpeedPAK!",
                "snippet": "Weitere Informationen liegen bei.",
                "body": "Ihre Sendung ist jetzt bei SpeedPAK! Weitere Informationen zu Ihrem eBay Kauf liegen bei.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "<fedex-de-gts-corr@fedex.com>",
                "subject": "Betreff：WICHTIG: Zustimmung zur Zollabfertigung für FedEx Sendung 884653092668",
                "snippet": "Für die Bearbeitung Ihrer Sendung benötigen wir Ihre Zustimmung zur Zollabfertigung.",
                "body": (
                    "Für die Bearbeitung Ihrer Sendung benötigen wir Ihre Zustimmung zur Zollabfertigung. "
                    "Bitte antworten Sie uns formlos auf diese E-Mail."
                ),
                "expected_labels": ["shopping-order"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_35_follow_on_families(self) -> None:
        cases = [
            {
                "sender": "eBay <ebay@ebay.com>",
                "subject": "💬 Gute Nachricht: KYOCERA GRATINA 4G… ist begehrt, aber noch limitiert verfügbar.",
                "snippet": "Wir kümmern uns darum, dass Sie nichts verpassen.",
                "body": "Gute Nachricht: Dieser Artikel ist begehrt, aber noch limitiert verfügbar.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "eBay <ebay@ebay.com>",
                "subject": "Nur noch 1 übrig: KYOCERA 902KC 903KC DIGNO 3 ANDROID FLIP PHONE SV UNLOCKED New w/Box",
                "snippet": "Nur noch 1 übrig.",
                "body": "Nur noch 1 übrig. Kaufen Sie jetzt bei eBay.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "eBay <ebay@ebay.com>",
                "subject": "Der Verkäufer bietet US $9,95 Rabatt auf [New] KYOCERA 902KC 903KC DIGNO Keitai 3...",
                "snippet": "Der Verkäufer bietet Rabatt.",
                "body": "Der Verkäufer bietet Rabatt auf Ihren beobachteten Artikel bei eBay.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "eBay <ebay@ebay.com>",
                "subject": "Der Verkäufer bietet US $10,25 Rabatt auf KYOCERA 902KC 903KC DIGNO 3 ANDROID FLIP...",
                "snippet": "Der Verkäufer bietet Rabatt.",
                "body": "Der Verkäufer bietet Rabatt auf Ihren beobachteten Artikel bei eBay.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Voi Technology <info@trans.voiapp.io>",
                "subject": "Updates to our privacy policy",
                "snippet": "We're updating our privacy policy.",
                "body": "We've made our privacy policy clearer and easier to navigate.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "COLE S MCLEOD <catch@payments.interac.ca>",
                "subject": "Interac e-Transfer: Your request for money $69.00 from COLE S MCLEOD has expired.",
                "snippet": "Your request for funds has expired.",
                "body": "Your request for money has expired. This is a secure transaction.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "Pantak  uae <fraud.alias@example.test>",
                "subject": "Employment Opportunity at Pantak Group LLC, UAE",
                "snippet": "We are pleased to inform you that your profile has been found suitable.",
                "body": (
                    "After reviewing your CV, please forward an updated copy to hr@pantakgroup.com "
                    "or fraud.contact@example.test for further evaluation."
                ),
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Ticketmaster <notification@email.ticketmaster.com>",
                "subject": "We're updating our terms and policies",
                "snippet": "Review updates to Ticketmaster US terms.",
                "body": "We're updating our Ticketmaster Terms of Use and Other Policies.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Google Photos <noreply-photos@google.com>",
                "subject": "You can no longer back up new photos or videos",
                "snippet": "Get more storage or clean up space.",
                "body": (
                    "You're out of storage and can't back up new photos or videos. "
                    "Get more storage with Google One membership or clean up space."
                ),
                "expected_labels": ["account-security"],
            },
            {
                "sender": '"service@intl.paypal.com" <service@intl.paypal.com>',
                "subject": "You sent a payment",
                "snippet": "Here's your receipt.",
                "body": "You sent €8.20 EUR. Transaction ID 80F59268D58583700. Here's your receipt.",
                "expected_labels": ["receipt-billing"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_36_mechanical_follow_on_families(self) -> None:
        cases = [
            {
                "sender": '"Battle.net" <noreply@battle.net>',
                "subject": "Battle.net Account Verification",
                "snippet": "Battle.net Account Verification.",
                "body": "Verify your Battle.net account to continue.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": '"Battle.net" <noreply@battle.net>',
                "subject": "Help us keep your Battle.net Account safe with a security check",
                "snippet": "Help us keep your Battle.net Account safe with a security check.",
                "body": "Help us keep your Battle.net Account safe with a security check.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": '"Battle.net" <noreply@battle.net>',
                "subject": "Battle.net Account - Password Change Notice",
                "snippet": "Your Battle.net password has been changed.",
                "body": "Battle.net Account password change notice.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Royal Mail <no-reply@royalmail.com>",
                "subject": "Ihr Royal Mail-Paket von Revival Books Ltd konnte nicht zugestellt werden",
                "snippet": "Ihr Royal Mail-Paket konnte nicht zugestellt werden.",
                "body": "Ihr Royal Mail-Paket von Revival Books Ltd konnte nicht zugestellt werden.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "DHL Paket <noreply@dhl.de>",
                "subject": "Ihre DHL Sendung liegt zur Abholung bereit",
                "snippet": "Ihre DHL Sendung liegt zur Abholung bereit.",
                "body": "Ihre DHL Sendung liegt ab sofort für Sie in der Filiale zur Abholung bereit.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": '"Berliner Büchertisch eG" <online@buechertisch.org>',
                "subject": "Ihre Bestellung über AbeBooks/ZVAB bei Berliner Büchertisch eG",
                "snippet": "Vielen Dank für Ihre Bestellung über AbeBooks/ZVAB.",
                "body": "Vielen Dank für Ihre Bestellung über AbeBooks/ZVAB. Mit folgendem Link können Sie den Sendungsstatus abrufen.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "medimops <noreply@medimops.de>",
                "subject": "Deine Rechnung DE-2025-14-000124349",
                "snippet": "Nochmals herzlichen Dank für deine Bestellung.",
                "body": "Nochmals herzlichen Dank für deine Bestellung im medimops Shop von AbeBooks. Im Anhang erhältst du die Rechnung.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": '"AbeBooks.de" <noreply_transactional@abebooks.de>',
                "subject": "AbeBooks Bestellnummer 751275822: Sendungsnummer hinzugefügt",
                "snippet": "Sendungsnummer hinzugefügt.",
                "body": "AbeBooks Bestellung 751275822: Sendungsnummer hinzugefügt. Logistikunternehmen und Sendungsnummer folgen.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": '"AbeBooks.de" <news@info.abebooks.de>',
                "subject": "Herzlich Willkommen bei AbeBooks!",
                "snippet": "Vielen Dank, dass Sie sich als Nutzer bei AbeBooks.de registriert haben.",
                "body": "Herzlich willkommen bei AbeBooks.de. Vielen Dank für Ihre Registrierung.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "COLE S MCLEOD <notify@payments.interac.ca>",
                "subject": "Interac e-Transfer: COLE S MCLEOD has requested $69.00 from you.",
                "snippet": "COLE S MCLEOD has requested $69.00 from you.",
                "body": "COLE S MCLEOD has requested $69.00 from you. Respond to transfer request. Expiry: Sept 5, 2025.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "GLS Paket <no-reply@gls-pakete.de>",
                "subject": "📦 Dein Paket wurde an einen Nachbarn übergeben",
                "snippet": "Dein Paket wurde an einen Nachbarn übergeben.",
                "body": "Dein Paket wurde an deinen Nachbarn übergeben und wartet auf deine Abholung.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "YouTube <noreply-purchases@youtube.com>",
                "subject": "Your membership to Apostolic Majesty",
                "snippet": "You've unlocked access to special perks and benefits.",
                "body": "You've unlocked access to special perks and benefits. Order Date.",
                "expected_labels": ["shopping-order"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_university_of_europe_followups_as_low_value(self) -> None:
        cases = [
            {
                "sender": "Jordan Example <university.contact@example.test>",
                "subject": "Your enquiry with University of Europe for Applied Sciences",
                "snippet": "I have not heard from you for a while. Are you still interested in joining us?",
                "body": (
                    "This is Hannah from the University of Europe for Applied Sciences. "
                    "I have not heard from you for a while. Are you still interested in joining us?"
                ),
            },
            {
                "sender": "Jordan Example <university.contact@example.test>",
                "subject": "Your enquiry with University of Europe for Applied Sciences",
                "snippet": "I am checking to see if you have decided to discuss your studies with us.",
                "body": (
                    "I am checking to see if you have decided to discuss your studies with us. "
                    "You can set the call with your advisor once we receive your response."
                ),
            },
            {
                "sender": "Jordan Example <university.contact@example.test>",
                "subject": "Your enquiry with University of Europe for Applied Sciences",
                "snippet": "I'm following up on your recent enquiry to study with us.",
                "body": (
                    "I'm following up on your recent enquiry to study with us. "
                    "Our Student Recruitment team can talk you through our programmes and visa guidance."
                ),
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        for item in review_queue["items"]:
            with self.subTest(snippet=item["snippet"]):
                self.assertEqual(item["applied_labels"], ["spam-low-value"])

    def test_classify_messages_marks_batch_37_shipping_and_order_families(self) -> None:
        cases = [
            {
                "sender": '"MB-Fahrrad-DE |  Der E-Bike und Fahrrad Profi Shop - Amazon Payments" '
                "<q0drsnd9wn9w2tq@marketplace.amazon.de>",
                "subject": "[Wichtig] Ihr Paket ist da!",
                "snippet": "Ihr DPD Paket ist da und kann abgeholt werden.",
                "body": "Ihr Paket ist da. Ihr DPD Paket kann jetzt abgeholt werden.",
            },
            {
                "sender": "DPD <noreply@service.dpd.de>",
                "subject": "Ihr Paket ist auf dem Weg zum Pickup Paketshop / Station",
                "snippet": "Ihr Paket ist auf dem Weg zum Pickup Paketshop / Station.",
                "body": "Guten Tag, Ihr Paket ist auf dem Weg zum Pickup Paketshop / Station.",
            },
            {
                "sender": "Emma from Alltricks <contact@alltricks.com>",
                "subject": "Your order has been shipped!",
                "snippet": "Order n° 250330T070793201A has been shipped.",
                "body": "Order n° 250330T070793201A. Your order has been shipped!",
            },
            {
                "sender": '"rueckgabe@amazon.de" <rueckgabe@amazon.de>',
                "subject": "Your return of Cycling Shoes",
                "snippet": "We've accepted your return request.",
                "body": "Hello Alex, We've accepted your return request. Once we've received the item below, we'll issue your refund.",
            },
            {
                "sender": "Chronopost <avisage-ne-pas-repondre@chronopost.fr>",
                "subject": "Your parcel is on its way XT313140971TS",
                "snippet": "Your parcel is being handled in our network.",
                "body": "Dear Customer, Your parcel is being handled in our network. Track your shipment by clicking here.",
            },
            {
                "sender": "Caventura GmbH <greatcoffee@caventura.com>",
                "subject": "Deine Caventura Bestellung wurde empfangen!",
                "snippet": "Wir haben deine Bestellung #16903 erhalten.",
                "body": "Danke für deine Bestellung. Wir haben deine Bestellung #16903 erhalten und werden sie umgehend bearbeiten.",
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        for item in review_queue["items"]:
            with self.subTest(subject=item["subject"]):
                self.assertEqual(item["applied_labels"], ["shopping-order"])

    def test_classify_messages_marks_batch_37_account_and_finance_families(self) -> None:
        cases = [
            {
                "sender": "Sun_Life_Financial@info.sunlife.ca",
                "subject": "Your Registration Code",
                "snippet": "Use the code below to continue your registration.",
                "body": "Your Registration Code. Use the code below to continue your registration.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Sun_Life_Financial@info.sunlife.ca",
                "subject": "Confirm your email address with Sun Life",
                "snippet": "Thanks for starting to register your online account.",
                "body": "Confirm your email address with Sun Life and continue with your registration.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "merlinhelp@birds.cornell.edu",
                "subject": "Username reminder",
                "snippet": "You already have the following Cornell Lab accounts.",
                "body": "Username reminder. Your Cornell Lab account lets you access these projects.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "noreply@td.com",
                "subject": "Avoid delays in your cheque(s) getting to you | Sign-up for Electronic Funds Transfer (EFT)",
                "snippet": "Canada Post services may be disrupted in the coming weeks.",
                "body": "Canada Post services may be disrupted in the coming weeks and paper cheques may be delayed. Sign-up for Electronic Funds Transfer.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "noreply@td.com",
                "subject": "Canada Post: Information about potential service disruption",
                "snippet": "Important information about a potential Canada Post service disruption.",
                "body": "Important information about a potential Canada Post service disruption and mail delivery delays.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "TYLER GODBOLT <notify@payments.interac.ca>",
                "subject": "Interac e-Transfer: TYLER GODBOLT sent you $113.00. Claim your deposit!",
                "snippet": "Your funds await. Select your financial institution to deposit funds.",
                "body": "Your funds await. Claim your deposit and select your financial institution to deposit funds.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "security_alerts@info.sunlife.ca",
                "subject": "You’ve added Two-Step Verification to your account",
                "snippet": "You recently added Two-Step Verification security to your account.",
                "body": "You recently added Two-Step Verification security to your account.",
                "expected_labels": ["account-security"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_37_low_value_personal_and_reply_needed_families(self) -> None:
        cases = [
            {
                "sender": "info4@medactionplan.com",
                "subject": "Reminder: Georgetown University Hospital has invited you to view your med list. Accept the MyMedSchedule connection to access it today",
                "snippet": "Georgetown University Hospital wants to share the medication list through MyMedSchedule Plus.",
                "body": "Georgetown University Hospital has invited you to help manage medicines through MyMedSchedule Plus. Accept the medication list connection.",
                "expected_labels": ["personal"],
            },
            {
                "sender": "Taylor Example <university.recruiting@example.test>",
                "subject": "Follow-up on your Inquiry at UE!",
                "snippet": "I tried to call you regarding your inquiry.",
                "body": "Follow-up on your Inquiry at UE! Book a MS Teams consultation with the University of Europe for Applied Sciences.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "xAI <noreply@x.ai>",
                "subject": "xAI Live Search API Beta",
                "snippet": "Live Search is now available in beta on the xAI API.",
                "body": "The Live Search API is now available in beta on the xAI API.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "iNaturalist Team <inaturalist@inaturalist.org>",
                "subject": "Thanks for joining the City Nature Challenge — here’s what’s next!",
                "snippet": "Help with CNC identifications.",
                "body": "Thanks for joining the City Nature Challenge. Help with CNC identifications and read on to learn more.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Julia - Wolt <Julia@mail.wolt.com>",
                "subject": "Update: Wolt Rewards",
                "snippet": "Please take a moment to read this.",
                "body": "Please take a moment to read this. Update: Wolt Rewards.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Alltricks Support <contact@alltricks.fr>",
                "subject": "Suite à la livraison de votre commande",
                "snippet": "Votre avis compte pour nous.",
                "body": "Bonjour Alex, Votre avis compte pour nous suite à la livraison de votre commande.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": " IMF iData <idata@imf.org>",
                "subject": "Upcoming Changes to IMF Data Portal",
                "snippet": "data.imf.org will be replaced with a new IMF Data Portal.",
                "body": "Upcoming Changes to IMF Data Portal. data.imf.org will be replaced with a new IMF Data Portal.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Morgan Friend <morgan.friend@example.test>",
                "subject": "My Packing List",
                "snippet": "Here is my packing list.",
                "body": "Here is my packing list just in case you wanted to work off of it as well. Or know what I plan to bring.",
                "expected_labels": ["personal"],
            },
            {
                "sender": "Kai Friend <kai.friend@example.test>",
                "subject": 'Kai Friend shared the folder "Photos with Andrew" with you',
                "snippet": "Kai Friend invited you to access a folder.",
                "body": "Kai Friend invited you to access a folder. Here's the folder that Kai Friend shared with you.",
                "expected_labels": ["personal"],
            },
            {
                "sender": "Tyler Godbolt <tyler.friend@example.test>",
                "subject": "Re: Follow-Up on Sword Feedback, Order #156279 (BrushWiz.com)",
                "snippet": "Please let me know what you think.",
                "body": "Please let me know what you think about the mock up. BrushWiz.com order #156279.",
                "expected_labels": ["reply-needed", "shopping-order"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_38_order_and_travel_families(self) -> None:
        cases = [
            {
                "sender": '"Audible.de" <donotreply@audible.de>',
                "subject": "Deine Bestellung bei Audible",
                "snippet": "Danke für deinen Einkauf.",
                "body": "Danke für deinen Einkauf. Bestellnummer: D01-5936094-4213445. Apple in-app Kauf.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": '"Audible.de" <do_not_reply@audible.de>',
                "subject": "Du hast Änderungen an deinem Abo vorgenommen",
                "snippet": "Hiermit bestätigen wir die Kündigung deines Audible-Abos.",
                "body": "Hiermit bestätigen wir die Kündigung deines Audible-Abos. Dein Abo endet am 23.03.2025.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Google Play <googleplay-noreply@google.com>",
                "subject": "Payment declined for YouTube subscription",
                "snippet": "Your subscription will be cancelled. Update payment.",
                "body": "Payment declined for YouTube subscription. Your subscription will be cancelled. Update payment.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Travelodge Website <webmaster@mail.travelodge.co.uk>",
                "subject": "Your Travelodge Invoice",
                "snippet": "VAT Invoice. Invoice Number: WB117131667.",
                "body": "Your Travelodge Invoice. VAT Invoice. Invoice Number: WB117131667.",
                "expected_labels": ["receipt-billing"],
            },
            {
                "sender": "Travelodge Website <webmaster@mail.travelodge.co.uk>",
                "subject": "Your Travelodge booking confirmation",
                "snippet": "Your booking is now confirmed. Confirmation Number: 71610632.",
                "body": "Your Travelodge booking confirmation. Your booking is now confirmed. Confirmation Number: 71610632.",
                "expected_labels": ["travel"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_38_account_and_finance_families(self) -> None:
        cases = [
            {
                "sender": "Amazon Prime <prime@amazon.de>",
                "subject": "Your Prime membership needs your attention",
                "snippet": "Your Prime membership needs your attention.",
                "body": "Your Prime membership needs your attention.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Bumble <hi@bumble.com>",
                "subject": "Bitte bestätige deine E-Mail Adresse",
                "snippet": "Klicke auf den Button, um deine E-Mail-Adresse zu bestätigen.",
                "body": "Bitte bestätige deine E-Mail Adresse. Klicke auf den Button, um deine E-Mail-Adresse zu bestätigen.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Google <google-noreply@google.com>",
                "subject": "Your Gmail storage is 86% full",
                "snippet": "Your Gmail storage is 86% full.",
                "body": "Your Gmail storage is 86% full.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "University of Europe for Applied Sciences <noreply@ue-germany.de>",
                "subject": "Application Portal – Account Activation",
                "snippet": "You have successfully signed up for the Application Portal.",
                "body": "Application Portal – Account Activation. You have successfully signed up for University of Europe for Applied Sciences Application Portal.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "noreply@x.ai",
                "subject": "New login to your xAI account",
                "snippet": "New login to your xAI account.",
                "body": "New login to your xAI account.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "noreply@td.com",
                "subject": "Important information about your accounts.",
                "snippet": "We've updated your statement delivery preferences to paperless.",
                "body": "We've updated your statement delivery preferences to paperless.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "KYLE RICHARD RUNDLE DRAKE <notify@payments.interac.ca>",
                "subject": "Interac e-Transfer: Your transfer from KYLE RICHARD RUNDLE DRAKE for $22.69 has expired",
                "snippet": "Your transfer has expired.",
                "body": "Interac e-Transfer: Your transfer from KYLE RICHARD RUNDLE DRAKE for $22.69 has expired.",
                "expected_labels": ["financial-account"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_38_low_value_and_personal_families(self) -> None:
        cases = [
            {
                "sender": "Google Developer Program <googledev-noreply@google.com>",
                "subject": "Welcome! Personalize your Google Developer Program journey",
                "snippet": "Personalize your Google Developer Program journey.",
                "body": "Welcome! Personalize your Google Developer Program journey.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Taylor Example <university.recruiting@example.test>",
                "subject": "You enquired about studying at the University of Europe for Applied Sciences (UE).",
                "snippet": "You enquired about studying at the University of Europe for Applied Sciences.",
                "body": "You enquired about studying at the University of Europe for Applied Sciences (UE). Book a MS Teams consultation.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Tyler Godbolt <tyler.friend@example.test>",
                "subject": "Andrews Wedding plans",
                "snippet": "We may stay in Banff and Canmore after the wedding.",
                "body": "As of right now we may stay in Banff and Canmore after the wedding. Throw out some accommodations options.",
                "expected_labels": ["personal"],
            },
            {
                "sender": "Filip Leskovec <hit-reply@linkedin.com>",
                "subject": "Enhancing API Adoption at Snap",
                "snippet": "Are you open to discussing this further?",
                "body": "I was curious about improving developer experience and API adoption. Are you open to discussing this further? I can set something up on your calendar.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Google Maps Timeline <noreply-maps-timeline@google.com>",
                "subject": "Alex, your November update",
                "snippet": "Here's your new Timeline update.",
                "body": "Here's your new Timeline update. You turned on Location History and can view, edit, and delete this data anytime in Timeline.",
                "expected_labels": ["spam-low-value"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_38_remaining_order_families(self) -> None:
        cases = [
            {
                "sender": "Audible Kundenservice <service@audible.de>",
                "subject": "Deine Anfrage bei Audible",
                "snippet": "Nachricht vom Kundenservice.",
                "body": "Nachricht vom Kundenservice. Es tut mir leid dass es ein Problem bei deinem Kauf gab. Gerne habe ich den Titel für dich gekauft.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "DHL Paket <noreply@dhl.de>",
                "subject": "Ihre Amazon Sendung liegt nebenan",
                "snippet": "Ihre Amazon Sendung ist angekommen. Wir haben sie bei Ralph Priebe abgegeben.",
                "body": "Ihre Amazon Sendung ist angekommen. Wir haben sie bei Ralph Priebe abgegeben.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": '"Amazon.de" <versandbestaetigung@amazon.de>',
                "subject": "Versendet: 3D Box",
                "snippet": "Dein Paket wurde versendet!",
                "body": "Dein Paket wurde versendet! Bestellt. Versendet. In Zustellung. Bestellnr.",
                "expected_labels": ["shopping-order"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_39_account_and_order_families(self) -> None:
        cases = [
            {
                "sender": "DHL EXPRESS <NoReply.ODD@dhl.com>",
                "subject": "DHL On Demand Delivery",
                "snippet": "Ihre DHL Express Sendung ist unterwegs.",
                "body": "DHL On Demand Delivery. Ihre DHL Express Sendung ist unterwegs.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Dropbox <no-reply@dropbox.com>",
                "subject": "Hi Alex, we noticed a new sign in to your Dropbox account",
                "snippet": "A new web browser just signed in to your Dropbox account.",
                "body": "A new web browser just signed in to your Dropbox account. Is this you?",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Google Wallet <googlewallet-noreply@google.com>",
                "subject": "Your card was deleted from your inactive Google Pixel 6 Pro",
                "snippet": "Your card was deleted from your inactive device.",
                "body": "Your card was deleted from your Google Pixel 6 Pro, an inactive device.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Gumroad <noreply@gumroad.com>",
                "subject": "Your authentication token is 281863",
                "snippet": "We have detected a new login to your Gumroad account.",
                "body": "Two-Factor Authentication. We have detected a new login to your Gumroad account. Enter this authentication token.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": '"amazon.de" <account-update@amazon.de>',
                "subject": "amazon.de: Account data access attempt",
                "snippet": "Someone is attempting to access your account data.",
                "body": "Someone is attempting to access your account data.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": 'diehandwerksprofis - Amazon Payments <q6n7w77mzhpwxkq@marketplace.amazon.de>',
                "subject": "Ihre Gutschrift zur Auftragsnummer 1888125",
                "snippet": "Ihre Gutschrift zur Auftragsnummer 1888125.",
                "body": "Ihre Gutschrift zur Auftragsnummer 1888125.",
                "expected_labels": ["shopping-order"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_39_personal_low_value_and_job_families(self) -> None:
        cases = [
            {
                "sender": "The Google Workspace Team <workspace-noreply@google.com>",
                "subject": "[Reminder] Jamboard application wind down",
                "snippet": "The Jamboard application will wind down on Dec 31, 2024.",
                "body": "The Jamboard application will wind down on Dec 31, 2024.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Indeed <no-reply@indeed.com>",
                "subject": "Neuer Job gesucht? Jetzt direkt Bewerbungsgespräch vereinbaren.",
                "snippet": "Online Job Event mit vielen Unternehmen deutschlandweit.",
                "body": "Neuer Job gesucht? Jetzt direkt Bewerbungsgespräch vereinbaren. Online Job Event.",
                "expected_labels": ["job-related"],
            },
            {
                "sender": "Adriana Veronezi <inmail-hit-reply@linkedin.com>",
                "subject": "Product Owner remote position",
                "snippet": "Send me your resume asap.",
                "body": "We have a Product Owner remote position. Send me your resume asap.",
                "expected_labels": ["job-related"],
            },
            {
                "sender": "WeTransfer <noreply@wetransfer.com>",
                "subject": "A transfer you sent is about to expire",
                "snippet": "A transfer you sent is about to expire.",
                "body": "A transfer you sent is about to expire.",
                "expected_labels": ["personal"],
            },
            {
                "sender": "Alex Friend <alex.friend@example.test>",
                "subject": "Dirty Mike and the boys.....",
                "snippet": "Thoughts regarding sleeping arrangements for Andrew's wedding.",
                "body": "Thoughts regarding sleeping arrangements for Andrew's wedding and teaming up for an Airbnb.",
                "expected_labels": ["personal"],
            },
            {
                "sender": '"Steve & Lyne" <family.contact@example.test>',
                "subject": "Berlin - Wittenberge - Havelberg - Berlin",
                "snippet": "An initial plan with hotel options.",
                "body": "An initial plan with hotel options for Berlin, Wittenberge, and Havelberg.",
                "expected_labels": ["personal"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_40_order_and_account_families(self) -> None:
        cases = [
            {
                "sender": '"OEL - Griechische Produkte und Olivenöl" <info@oel-berlin.de>',
                "subject": "Bestellung S4921 bestätigt",
                "snippet": "Vielen Dank für deinen Einkauf.",
                "body": "Vielen Dank für deinen Einkauf. Bestellung S4921.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Steam Team <noreply@steampowered.com>",
                "subject": "New sign in to Steam",
                "snippet": "New sign in to Steam.",
                "body": "New sign in to Steam. Authorized by: Steam Guard code from your email.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "TELUS <telusservice@i.telus.com>",
                "subject": "TELUS Public Wi-Fi: Activate your Account",
                "snippet": "Activate your account.",
                "body": "TELUS Public Wi-Fi: Activate your Account.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Google Play <googleplay-noreply@google.com>",
                "subject": "Changes to purchase verification settings on Google Play",
                "snippet": "You'll now use your face or fingerprint to verify it's you.",
                "body": "You've updated your Google Play purchase verification settings. You'll now use your face or fingerprint to verify it's you.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "<ASUS_member@asus.com>",
                "subject": "Welcome to be ASUS Account!",
                "snippet": "Verify your e-mail account.",
                "body": "Thank you for registering ASUS Account. Verify your e-mail account.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Amazon <account-update@amazon.com>",
                "subject": "Du hast einen Passkey für Amazon eingerichtet.",
                "snippet": "Du hast deinen Passkey erfolgreich eingerichtet.",
                "body": "Du hast deinen Passkey erfolgreich eingerichtet.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Amazon <account-update@amazon.ca>",
                "subject": "Passkey added to your account",
                "snippet": "A passkey was added to your Amazon account.",
                "body": "A passkey was added to your Amazon account.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": '"Amazon.de" <order-update@amazon.de>',
                "subject": "Delivery attempted with your Amazon package.",
                "snippet": "Unfortunately, DHL ran into an issue when attempting your delivery.",
                "body": "Delivery attempted with your Amazon package. Track your delivery.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "appsupport@bvg.de",
                "subject": "BVG – Order Confirmation: BF2024072400011206",
                "snippet": "The ticket has already been created.",
                "body": "Order Confirmation. The ticket has already been created and delivered into the app.",
                "expected_labels": ["travel"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_protonmail_discovery_records_with_approved_labels(self) -> None:
        cases = [
            {
                "sender": "<keine-antwort@handyticket.de>",
                "subject": "HandyTicket Deutschland: Quittung für den Ticketkauf",
                "snippet": "Quittung für den Ticketkauf.",
                "body": "HandyTicket Deutschland: Quittung für den Ticketkauf.",
                "expected_labels": ["travel", "receipt-billing"],
            },
            {
                "sender": "\"GitHub\" <noreply@github.com>",
                "subject": "[GitHub] A third-party OAuth application has been added to your account",
                "snippet": "A third-party OAuth application has been added to your account.",
                "body": "A third-party OAuth application has been added to your account.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "\"noreply@zoxs.de\" <noreply@zoxs.de>",
                "subject": "Statusupdate zu Deiner Bestellung 942964",
                "snippet": "Statusupdate zu Deiner Bestellung.",
                "body": "Statusupdate zu Deiner Bestellung 942964.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "\"Caventura GmbH\" <accounting@caventura.com>",
                "subject": "Versand Ihrer Bestellung 2002639 von Caventura GmbH",
                "snippet": "Versand Ihrer Bestellung.",
                "body": "Versand Ihrer Bestellung 2002639 von Caventura GmbH.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "\"Caventura GmbH\" <accounting@caventura.com>",
                "subject": "Lieferschein 3002664 von Caventura GmbH zum Auftrag 2002639",
                "snippet": "Lieferschein zum Auftrag.",
                "body": "Lieferschein 3002664 von Caventura GmbH zum Auftrag 2002639.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "<bilety@polregio.pl>",
                "subject": "🚄 Your ticket valid on 06-04-2026, Szczecin Główny ➔ Kostrzyn",
                "snippet": "Your ticket valid on 06-04-2026.",
                "body": "Your ticket valid on 06-04-2026, Szczecin Główny ➔ Kostrzyn.",
                "expected_labels": ["travel"],
            },
            {
                "sender": "\"Shopify Billing\" <billing@shopify.com>",
                "subject": "Jun 5, 2026 bill for Food Healthy",
                "snippet": "Your Shopify bill is ready.",
                "body": "Jun 5, 2026 bill for Food Healthy.",
                "expected_labels": ["receipt-billing"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"message-{index}",
                    "date": f"2026-06-19T08:{index:02d}:00Z",
                    "gmail_label_ids": [],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "source": "protonmail",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_second_protonmail_discovery_slice_records(self) -> None:
        cases = [
            {
                "sender": "\"Charles Schwab & Co., Inc.\" <donotreply@mail.schwab.com>",
                "subject": "Your account eStatement is available",
                "snippet": "Charles Schwab & Co., Inc.",
                "body": "Your account eStatement is available online.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "\"DHL Paket\" <noreply@dhl.de>",
                "subject": "Einlieferungsbeleg: Ihr Versand an der Packstation",
                "snippet": "Einlieferungsbeleg für Ihren Versand an der Packstation.",
                "body": "Einlieferungsbeleg: Ihr Versand an der Packstation.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "\"Steam Support\" <noreply@steampowered.com>",
                "subject": "Thank you for your Steam purchase!",
                "snippet": "Thanks for your purchase.",
                "body": "Thank you for your Steam purchase! Billing and payment details are available in your account.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "\"Proton\" <no-reply@notify.proton.me>",
                "subject": "Subscription has been renewed",
                "snippet": "Subscription has been renewed.",
                "body": "Subscription has been renewed. Your Proton subscription was renewed successfully.",
                "expected_labels": ["receipt-billing"],
            },
            {
                "sender": "<no-reply@winsim.de>",
                "subject": "Ihre winSIM-Rechnung",
                "snippet": "winSIM Rechnung",
                "body": "Die aktuelle Mobilfunkrechnung für Ihre Rufnummer können Sie in Ihrer Servicewelt abrufen.",
                "expected_labels": ["receipt-billing"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"message-{index}",
                    "date": f"2026-06-19T09:{index:02d}:00Z",
                    "gmail_label_ids": [],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "source": "protonmail",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_40_low_value_personal_and_finance_families(self) -> None:
        cases = [
            {
                "sender": "Julia - Wolt <Julia@mail.wolt.com>",
                "subject": "Important Update: New Verification Feature for Your Wolt Orders",
                "snippet": "New verification feature for your Wolt orders.",
                "body": "Important Update: New Verification Feature for Your Wolt Orders.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": '"Audible.de" <noreply@audible.de>',
                "subject": "Nicht vergessen: 2 Monate gehen auf uns!",
                "snippet": "Dein Prime-Vorteil wartet: 2 kostenlose Monate.",
                "body": "Dein Prime-Vorteil wartet: 2 kostenlose Monate.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Slack <feedback@slack.com>",
                "subject": "Notice of Slack’s new content deletion policy for free workspaces",
                "snippet": "Content older than one year will be deleted on free workspaces.",
                "body": "Notice of Slack’s new content deletion policy for free workspaces.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Patreon <no-reply@patreon.com>",
                "subject": "Monthly update: Catch up on posts from The Adam Friedland Show",
                "snippet": "Monthly update: Catch up on posts.",
                "body": "Monthly update: Catch up on posts from The Adam Friedland Show.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": '"Gîte l\'Oasis" <guesthouse@example.test>',
                "subject": "Re: Demande de réservation reçue depuis www.gite-oasis.fr",
                "snippet": "Nous n'avons plus de place pour ce soir. Voici la liste des hôtels.",
                "body": "Nous n'avons plus de place pour ce soir. Voici la liste des hôtels dans le village.",
                "expected_labels": ["travel"],
            },
            {
                "sender": "<service@insightpestsolutions.net>",
                "subject": "Service Reminder",
                "snippet": "Service Reminder.",
                "body": "Service Reminder from Insight Pest Solutions.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "TD Canada Trust <email@e.email-td.com>",
                "subject": "Important: Fraud prevention steps",
                "snippet": "How to help protect yourself and your finances from scams.",
                "body": "Important: Fraud prevention steps.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": '"Steve & Lyne" <family.contact@example.test>',
                "subject": "Berlin - Wittenberge - Havelberg - Berlin",
                "snippet": "An initial plan with hotel options.",
                "body": "An initial plan with hotel options for Wittenberge and Havelberg.",
                "expected_labels": ["personal"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_41_order_account_and_finance_families(self) -> None:
        cases = [
            {
                "sender": "TD <TD.Webbroker@td.com>",
                "subject": "Your TD Direct Investing account statement(s) is/are available",
                "snippet": "Your statement(s) is/are posted on eServices.",
                "body": "Your TD Direct Investing account statement is posted on eServices.",
                "expected_labels": ["financial-account"],
            },
            {
                "sender": '"Google’s Find My Device" <noreply-findmydevice@google.com>',
                "subject": "Find My Device network is on for your Pixel 6 Pro",
                "snippet": "Find My Device network is on.",
                "body": "Find My Device network is on for your Pixel 6 Pro.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "myDPD <no-reply@dpd.de>",
                "subject": "Verfolgen Sie Ihr Paket 02605008765599.",
                "snippet": "Ihr Paket ist auf dem Weg zu Ihnen.",
                "body": "Verfolgen Sie Ihr Paket. Ihr Paket ist auf dem Weg zu Ihnen.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "YouTube <noreply-purchases@youtube.com>",
                "subject": "Your YouTube receipt",
                "snippet": "Thanks for purchasing Boogie Nights on YouTube.",
                "body": "Your YouTube receipt. Purchase details.",
                "expected_labels": ["receipt-billing"],
            },
            {
                "sender": "DHL Paket <noreply@dhl.de>",
                "subject": "Digitaler Einlieferungsbeleg für Ihre DHL Retoure",
                "snippet": "Sie haben Ihre Retoure erfolgreich an DHL übergeben.",
                "body": "Digitaler Einlieferungsbeleg für Ihre DHL Retoure.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Amazon Pay <no-reply@amazon.com>",
                "subject": "Ihre Zahlung an AF Marcotec ist abgeschlossen.",
                "snippet": "Ihre Zahlung ist abgeschlossen.",
                "body": "Ihre Zahlung an AF Marcotec ist abgeschlossen. Vielen Dank, dass Sie Amazon Pay verwenden.",
                "expected_labels": ["receipt-billing"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_41_low_value_booking_and_personal_families(self) -> None:
        cases = [
            {
                "sender": "NETELLER Communications <communications@news.neteller.com>",
                "subject": "Important Notice Regarding Deposit and Withdrawal Fees",
                "snippet": "Upcoming changes to deposit and withdrawal fees.",
                "body": "Important Notice Regarding Deposit and Withdrawal Fees.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Jollyes <noreply.invitations@trustpilotmail.com>",
                "subject": "How many stars would you give Jollyes The Pet People?",
                "snippet": "How did we do?",
                "body": "How many stars would you give Jollyes The Pet People?",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": '"Martyna from BAD AXE Throwing Kraków" <badaxe@badaxe.pl>',
                "subject": "BAD AXE - przypomnienie o zadatku",
                "snippet": "Przypominamy o konieczności wysłania zadatku.",
                "body": "Przypomnienie o zadatku. Kwota zadatku: 140 PLN.",
                "expected_labels": ["calendar-event"],
            },
            {
                "sender": "Piotr from BAD AXE Throwing Krakow <badaxe@badaxe.pl>",
                "subject": "Wizyta BAD AXE",
                "snippet": "Wymagamy wpłaty 20% zadatku.",
                "body": "Wizyta BAD AXE. Wymagamy wpłaty 20% zadatku.",
                "expected_labels": ["calendar-event"],
            },
            {
                "sender": "Sun Life <sunlife@info.sunlife.ca>",
                "subject": "New updates to your Retirement Planner",
                "snippet": "Your updated tool gives you more features.",
                "body": "Updates to the Sun Life Retirement Planner.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Sun Life <sunlife@messages.sunlife.com>",
                "subject": "Alex, enrol and contribute and watch your TFSA grow tax-free!",
                "snippet": "Watch your TFSA grow tax-free.",
                "body": "Enrol and contribute and watch your TFSA grow tax-free.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Xe Money Transfer <xe@service.xe.com>",
                "subject": "A new experience for your Xe account",
                "snippet": "We now support Dutch, French, German, and Spanish.",
                "body": "A new experience for your Xe account.",
                "expected_labels": ["spam-low-value"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_42_account_and_order_families(self) -> None:
        cases = [
            {
                "sender": "Zoom <no-reply@zoom.us>",
                "subject": "Your Zoom password has been reset.",
                "snippet": "Your Zoom password has been reset.",
                "body": "Your Zoom password has been reset.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": '"Przelewy24.pl" <info@przelewy24.pl>',
                "subject": "Nowa transakcja płatnicza (P24-G1M-B3Y-D5T)",
                "snippet": "Nowa transakcja płatnicza.",
                "body": "Nowa transakcja płatnicza.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "visando - Amazon Payments <xgv1y3fh9w0ppqy@marketplace.amazon.de>",
                "subject": "Ware mit der Auftragsnummer ist unterwegs",
                "snippet": "Ware mit der Auftragsnummer ist unterwegs.",
                "body": "Ware mit der Auftragsnummer ist unterwegs. Vielen Dank für Ihren Einkauf.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": '"Google’s Find My Device" <noreply-findmydevice@google.com>',
                "subject": "Your Android devices will soon join the Find My Device network",
                "snippet": "Your Android devices will soon join the Find My Device network.",
                "body": "Your Android devices will soon join the Find My Device network.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "YouTube <noreply-purchases@youtube.com>",
                "subject": "Your YouTube receipt",
                "snippet": "Purchase details.",
                "body": "Your YouTube receipt. Purchase details.",
                "expected_labels": ["receipt-billing"],
            },
            {
                "sender": "Google Play <googleplay-noreply@google.com>",
                "subject": "Your trial for YouTube will end on 3 Apr 2024",
                "snippet": "Your trial will end.",
                "body": "Your trial for YouTube will end on 3 Apr 2024. Subscription benefits.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Discord <noreply@discord.com>",
                "subject": "Discord Account Scheduled for Deletion",
                "snippet": "Log in now to keep your account.",
                "body": "Discord Account Scheduled for Deletion on Apr 4, 2024. Log in now to keep your account.",
                "expected_labels": ["account-security"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_42_low_value_and_newsletter_families(self) -> None:
        cases = [
            {
                "sender": '"Audible.de" <noreply@audible.de>',
                "subject": "Audible 3 Monate für je nur 2,95 €/Monat + 15 € Audible Guthaben.",
                "snippet": "3 Monate für je nur 2,95 €/Monat.",
                "body": "Audible 3 Monate für je nur 2,95 €/Monat + 15 € Audible Guthaben.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Patreon <bingo@patreon.com>",
                "subject": "The Adam Friedland Show just shared",
                "snippet": "The Adam Friedland Show just shared.",
                "body": "The Adam Friedland Show just shared a post.",
                "expected_labels": ["newsletter"],
            },
            {
                "sender": "Microsoft Rewards <MicrosoftRewards@emailnotify.microsoft.com>",
                "subject": "Your Microsoft Rewards points will expire soon",
                "snippet": "Points will expire soon.",
                "body": "Your Microsoft Rewards points will expire soon.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Learning Newsletter <learning.newsletter@example.test>",
                "subject": "Learn to code Nest.js apps",
                "snippet": "Free 12-hour course.",
                "body": "Learn to code Nest.js apps. Free 12-hour course on Full-Stack JavaScript.",
                "expected_labels": ["newsletter"],
            },
            {
                "sender": "hello@bookyourhunt.com",
                "subject": "Alex, get only the hunts you want!",
                "snippet": "Get only the hunts you want.",
                "body": "Get only the hunts you want.",
                "expected_labels": ["spam-low-value"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_batch_43_families(self) -> None:
        cases = [
            {
                "sender": "DHL Paket <noreply@dhl.de>",
                "subject": "Jetzt live verfolgen - Ihr Amazon Paket kommt heute...",
                "snippet": "Ihr Amazon Paket kommt heute.",
                "body": "Jetzt live verfolgen - Ihr Amazon Paket kommt heute.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "YouTube <noreply-purchases@youtube.com>",
                "subject": "Welcome to YouTube Premium",
                "snippet": "Welcome to YouTube Premium.",
                "body": "Welcome to YouTube Premium. Manage and cancel anytime.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "noreply@1se.co",
                "subject": "Your inactive 1SE account has been deleted.",
                "snippet": "Your inactive 1SE account has been deleted.",
                "body": "Your inactive 1SE account has been deleted.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Discord <notifications@discord.com>",
                "subject": "Update your username by March 4, 2024",
                "snippet": "Update your username by March 4, 2024.",
                "body": "Update your username by March 4, 2024.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Reddit <noreply@redditmail.com>",
                "subject": "Updates to Reddit’s Privacy Policy and User Agreement",
                "snippet": "Updates to Privacy Policy and User Agreement.",
                "body": "Updates to Reddit’s Privacy Policy and User Agreement.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": '"return@amazon.com" <return@amazon.com>',
                "subject": "Let us know how we did - Amazon Product Support",
                "snippet": "Let us know how we did.",
                "body": "Let us know how we did - Amazon Product Support.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "David Friend <david.friend@example.test>",
                "subject": "Please join Zoom meeting in progress",
                "snippet": "Please join Zoom meeting in progress.",
                "body": "Please join Zoom meeting in progress.",
                "expected_labels": ["personal"],
            },
            {
                "sender": "Daniel Cole <dan.friend@example.test>",
                "subject": "Re: Reading Determined",
                "snippet": "Reading Determined.",
                "body": "Re: Reading Determined.",
                "expected_labels": ["personal"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    "sender": case["sender"],
                    "subject": case["subject"],
                    "snippet": case["snippet"],
                    "body": case["body"],
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_subject = {item["subject"]: item["applied_labels"] for item in review_queue["items"]}
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(labels_by_subject[case["subject"]], case["expected_labels"])

    def test_classify_messages_marks_exact_trusted_personal_sender_as_personal(self) -> None:
        classifier = FixtureBatchClassifier(
            fixtures_dir=Path("."),
            trusted_personal_senders={"sophie.friend@example.test"},
        )
        review_queue = classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Sophie Friend <sophie.friend@example.test>",
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
            trusted_personal_senders={"sophie.friend@example.test"},
        )
        review_queue = classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": "gmail-live-001",
                    "sender": "Sophie Friend <totally-different@example.com>",
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

    def test_classify_messages_marks_batch_44_pending_families(self) -> None:
        cases = [
            {
                "sender": "Wise <noreply@wise.com>",
                "subject": "We’ve had to restrict your account",
                "snippet": "Wise. Your account for the world's money.",
                "body": "We’ve had to restrict your account.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Insight Pest Solutions <noreply@workwave.com>",
                "subject": "Complete Verification",
                "snippet": "Welcome to your Customer Portal. Click the button below to verify your account.",
                "body": "Welcome to your Customer Portal. Click the button below to verify your account.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Slack <no-reply-9cHULhR0IDmxUhselWhRo6Hr@slack.com>",
                "subject": "Slack confirmation code: XXP-UFJ",
                "snippet": "Confirm your email address.",
                "body": (
                    "Confirm your email address. Your confirmation code is below — enter it in your open browser "
                    "window and we'll help you get signed in."
                ),
                "expected_labels": ["account-security"],
            },
            {
                "sender": "Amazon Prime <prime@amazon.de>",
                "subject": "An update on Prime Video",
                "snippet": "An update on Prime Video.",
                "body": (
                    "We are writing to you today about an upcoming change to your Prime Video experience. "
                    "Starting February 5, Prime Video movies and TV shows will include limited advertisements. "
                    "We will also offer a new ad-free option for an additional €2.99 per month."
                ),
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Amazon Prime <prime@amazon.com>",
                "subject": "An update on Prime Video",
                "snippet": "An update on Prime Video.",
                "body": (
                    "We are writing to you today about an upcoming change to your Prime Video experience. "
                    "Starting January 29, Prime Video movies and TV shows will include limited advertisements. "
                    "We will also offer a new ad-free option for an additional $2.99 per month."
                ),
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "OpenAI <noreply@email.openai.com>",
                "subject": "Aktualisierungen unserer Nutzungsbedingungen & Datenschutzerklärung",
                "snippet": "Wir möchten Sie über einige bevorstehende Änderungen informieren.",
                "body": (
                    "Wir möchten Sie über einige bevorstehende Änderungen unserer Nutzungsbedingungen und "
                    "Datenschutzerklärung informieren."
                ),
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Sun Life <sunlife@messages.sunlife.com>",
                "subject": "Coming soon: 2023 tax slips and receipts.",
                "snippet": "Switch to Paperless and download tax slips right away.",
                "body": (
                    "We’re putting your 2023 tax forms for your Choices savings plan online as soon as they’re "
                    "ready. Switch to Paperless today and access your tax slips and receipts."
                ),
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "Wise <noreply@wise.com>",
                "subject": "Confirm your details by 10 January",
                "snippet": "Wise. Your account for the world's money.",
                "body": "Confirm your details by 10 January to keep using your Wise account.",
                "expected_labels": ["account-security"],
            },
            {
                "sender": '"Amazon.de" <order-update@amazon.de>',
                "subject": "Delivery update: Karrong Haken Selbstklebend...",
                "snippet": "Your package is on the way but running late.",
                "body": "Your package is on the way but running late. Track your delivery for the latest updates.",
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "Bittrex Global <no-reply@global.bittrex.com>",
                "subject": "Bittrex Global: Trading now suspended",
                "snippet": "Trading now suspended.",
                "body": (
                    "Trading on Bittrex Global was suspended as of 18:00 UTC today. Your client relationship "
                    "has now been terminated and all activity on the platform except the ability to withdraw "
                    "has been disabled."
                ),
                "expected_labels": ["financial-account"],
            },
            {
                "sender": '"Alex Example (via Google Docs)" <drive-shares-dm-noreply@google.com>',
                "subject": 'Document shared with you: "Meditations"',
                "snippet": "Alex Example shared a document.",
                "body": "I've shared an item with you: Meditations.",
                "expected_labels": ["personal"],
            },
            {
                "sender": '"Alex Example (via Google Docs)" <drive-shares-dm-noreply@google.com>',
                "subject": 'Document shared with you: "Deep Work"',
                "snippet": "Alex Example shared a document.",
                "body": "I've shared an item with you: Deep Work.",
                "expected_labels": ["personal"],
            },
            {
                "sender": "Newsletter Author <newsletter.author@example.test>",
                "subject": "Project Management Professional (PMP) Certification Training",
                "snippet": "An extraordinary opportunity that has the potential to reshape your career.",
                "body": "We are delighted to introduce you to the PMP Certification Training Course.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "MGM Resorts Cybersecurity Notification <mgmresortsnotification@cyberscout.com>",
                "subject": "Important Information About Cybersecurity Issue",
                "snippet": "Please read this message in its entirety.",
                "body": "Important information about cybersecurity issue affecting MGM Resorts.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Newsletter Author <newsletter.author@example.test>",
                "subject": "Join our Live Online CSPO® Certification Training",
                "snippet": "A transformative opportunity.",
                "body": "We are excited to introduce the Certified Scrum Product Owner Certification Training.",
                "expected_labels": ["spam-low-value"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_case = {
            (item["sender"], item["subject"]): item["applied_labels"] for item in review_queue["items"]
        }
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(
                    labels_by_case[(case["sender"], case["subject"])],
                    case["expected_labels"],
                )

    def test_classify_messages_marks_batch_45_pending_families(self) -> None:
        cases = [
            {
                "sender": "Newsletter Author <newsletter.author@example.test>",
                "subject": "Elevate Your Agile Product Ownership with SAFe® 6.0 POPM Certification",
                "snippet": "We are excited to announce our upcoming SAFe 6.0 Product Owner/Product Manager Certification Training Course.",
                "body": "We invite you to join our SAFe 6.0 Product Owner/Product Manager Certification Training Course.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "Bittrex Global <no-reply@global.bittrex.com>",
                "subject": " Important Update Regarding Bittrex Global ",
                "snippet": "Bittrex Global has decided to wind down its operations.",
                "body": (
                    "Bittrex Global has decided to wind down its operations. Based on our records, you have no "
                    "funds on Bittrex Global. This email is for information only; no action is required from you."
                ),
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "Sebastian Friend <sebastian.friend@example.test>",
                "subject": "Fit Analytics Update",
                "snippet": "It has been seven weeks since Snap's announcement about closing ARES.",
                "body": (
                    "Dear FitAers, it has been seven weeks since Snap's announcement about closing ARES. "
                    "I've been actively engaged in discussions with Snap to regain ownership in Fit Analytics. "
                    "Project Phoenix is designed to reposition Fit Analytics for sustained success."
                ),
                "expected_labels": ["job-related"],
            },
            {
                "sender": "Soundiiz <info@soundiiz.com>",
                "subject": "Scheduled Soundiiz account deletion",
                "snippet": "Sign back into Soundiiz web application to keep your account.",
                "body": (
                    "Your account and data in Soundiiz will be deleted on 2024-01-14 after more than 36 months "
                    "of inactivity. Sign back into Soundiiz again before the scheduled deletion date."
                ),
                "expected_labels": ["account-security"],
            },
            {
                "sender": '"Amazon.de Rezensionen" <customer-reviews-messages@amazon.de>',
                "subject": "Alex Example, ever wonder if your reviews are getting noticed?",
                "snippet": "They are. Keep it up by reviewing more products.",
                "body": "They are. Keep it up by reviewing more products. Your views: 2,000+ Your helpful votes: 15.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "DHL Paket <noreply@dhl.de>",
                "subject": "Es tut uns leid - Ihr Amazon Paket verspätet sich.",
                "snippet": "Ursprünglich sollte Ihr Amazon Paket heute ankommen.",
                "body": (
                    "Es tut uns leid - Ihr Amazon Paket verspätet sich. Ursprünglich sollte Ihr Amazon Paket "
                    "heute ankommen. Leider kam es auf dem Transportweg zu unerwarteten Verzögerungen."
                ),
                "expected_labels": ["shopping-order"],
            },
            {
                "sender": "noReply.dfd@goethe.de",
                "subject": "Deutsch für dich | News November 2023",
                "snippet": "News from the Deutsch für dich Team.",
                "body": 'Deutsch für dich - News from the "Deutsch für dich" Team.',
                "expected_labels": ["newsletter"],
            },
            {
                "sender": "Newsletter Author <newsletter.author@example.test>",
                "subject": "SAFe® 6.0 Product Owner/Product Manager (POPM) Training",
                "snippet": "We are excited to introduce our upcoming SAFe 6.0 Product Owner/Product Manager Certification Training Course.",
                "body": "Our upcoming SAFe 6.0 Product Owner/Product Manager Certification Training Course is now open.",
                "expected_labels": ["spam-low-value"],
            },
            {
                "sender": "noreply-onlineaccess@td.com",
                "subject": "TD – New Device Login",
                "snippet": "We noticed a sign in from a new device.",
                "body": (
                    "We noticed a sign in from a new device with your username, password, and security code. "
                    "If you don't recognize this login, please immediately change your password."
                ),
                "expected_labels": ["account-security"],
            },
            {
                "sender": "KYLE RICHARD RUNDLE DRAKE <notify@payments.interac.ca>",
                "subject": "INTERAC e-Transfer: Remember to deposit your money from KYLE RICHARD RUNDLE DRAKE by November 18, 2023.",
                "snippet": "Sent you a money transfer. Deposit your money now.",
                "body": (
                    "KYLE RICHARD RUNDLE DRAKE sent you a money transfer. To receive your money, you must "
                    "deposit it by November 18, 2023."
                ),
                "expected_labels": ["financial-account"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_case = {
            (item["sender"], item["subject"]): item["applied_labels"] for item in review_queue["items"]
        }
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(
                    labels_by_case[(case["sender"], case["subject"])],
                    case["expected_labels"],
                )

    def test_classify_messages_marks_batch_46_pending_families(self) -> None:
        cases = [
            {
                "sender": "KYLE RICHARD RUNDLE DRAKE <notify@payments.interac.ca>",
                "subject": "INTERAC e-Transfer: KYLE RICHARD RUNDLE DRAKE sent you money.",
                "snippet": "KYLE RICHARD RUNDLE DRAKE sent you $161.96 (CAD). Deposit your money.",
                "body": (
                    "KYLE RICHARD RUNDLE DRAKE sent you a money transfer for the amount of $161.96 (CAD). "
                    "To deposit your money, click here."
                ),
                "expected_labels": ["financial-account"],
            },
            {
                "sender": "Nicole Kruckmeyer <recruiter@example.test>",
                "subject": "Re: Wind Down Team FAQs",
                "snippet": "Once we get the signed copies in the mail, we will be reinstating your accounts.",
                "body": "Once we get the signed copies in the mail, we will be reinstating your accounts.",
                "expected_labels": ["job-related"],
            },
            {
                "sender": "Sebastian Friend <sebastian.friend@example.test>",
                "subject": "Re: Wind Down Team FAQs",
                "snippet": "What is a messenger platform that works for you and that we can utilize for team communication?",
                "body": "The new FitA slack instance is not ideal since private groups are not possible.",
                "expected_labels": ["job-related"],
            },
            {
                "sender": "Alex Example <alex@example.com>",
                "subject": "Re: Wind Down Team FAQs",
                "snippet": "Please find the scans of my signatures.",
                "body": "Please find the scans of my signatures. The paper signed copies will be mailed today.",
                "expected_labels": ["job-related"],
            },
            {
                "sender": "Nicole Kruckmeyer <recruiter@example.test>",
                "subject": "Wind Down Team FAQs",
                "snippet": "",
                "body": "",
                "expected_labels": ["job-related"],
            },
        ]

        review_queue = self.classifier.classify_messages(
            "founder-test-batch-x",
            [
                {
                    "message_id": f"gmail-live-{index:03d}",
                    "date": "2026-06-19T08:00:00Z",
                    "gmail_label_ids": ["INBOX", "CATEGORY_UPDATES"],
                    "list_unsubscribe": None,
                    "precedence": "",
                    **case,
                }
                for index, case in enumerate(cases, 1)
            ],
        )

        labels_by_case = {
            (item["sender"], item["subject"]): item["applied_labels"] for item in review_queue["items"]
        }
        for case in cases:
            with self.subTest(subject=case["subject"]):
                self.assertEqual(
                    labels_by_case[(case["sender"], case["subject"])],
                    case["expected_labels"],
                )


if __name__ == "__main__":
    unittest.main()
