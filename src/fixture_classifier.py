import json
from datetime import UTC, datetime
from pathlib import Path

from src.sender_utils import normalized_sender_email


class FixtureBatchClassifier:
    def __init__(self, fixtures_dir: Path, trusted_personal_senders: set[str] | None = None) -> None:
        self._fixtures_dir = fixtures_dir
        self._trusted_personal_senders = trusted_personal_senders or set()

    def classify_fixture_batch(self, batch_id: str) -> dict:
        batch_path = self._fixtures_dir / f"{batch_id}.json"
        batch = json.loads(batch_path.read_text())

        return self.classify_messages(batch["batch_id"], batch["messages"])

    def classify_messages(self, batch_id: str, messages: list[dict]) -> dict:
        return {
            "batch_id": batch_id,
            "items": sorted(
                [self._classify_message(message) for message in messages],
                key=self._sort_key,
            ),
        }

    def _classify_message(self, message: dict) -> dict:
        subject = message["subject"].lower()
        body = message["body"].lower()
        snippet = (message.get("snippet") or "").lower()
        sender = message.get("sender", "").lower()
        sender_email = normalized_sender_email(message.get("sender"))
        list_unsubscribe = (message.get("list_unsubscribe") or "").lower()
        precedence = (message.get("precedence") or "").lower()
        gmail_label_ids = {label.lower() for label in message.get("gmail_label_ids", [])}
        text = f"{subject} {snippet} {body} {sender} {list_unsubscribe}".strip()
        header_text = f"{subject} {snippet} {sender}".strip()

        labels: list[str] = []
        near_misses: list[str] = []
        confidence_band = "low"

        if (
            "travel itinerary" in text
            and "receipt" in text
            and "calendar" in text
            and "personal" in text
        ):
            labels.extend(["travel", "receipt-billing", "calendar-event", "personal"])
            confidence_band = "medium"
        elif self._looks_like_job_application_message(text, sender):
            labels.append("job-related")
            near_misses.append("reply-needed")
            confidence_band = "medium"
        elif self._looks_like_job_alert_message(text, sender):
            labels.append("job-related")
            confidence_band = "medium"
        elif self._looks_like_google_play_receipt(text, sender):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_requested_promo_message(text):
            labels.append("promotions")
            confidence_band = "medium"
        elif self._looks_like_reply_needed_text(text) and not self._looks_like_legal_notice(text, sender):
            labels.extend(["reply-needed", "job-related"])
            confidence_band = "high"
        elif self._looks_like_account_message(text, sender, gmail_label_ids):
            labels.append("account-security")
            near_misses.append("reply-needed")
            confidence_band = "high"
        elif self._looks_like_payment_scam_message(text, sender, gmail_label_ids, list_unsubscribe, precedence):
            labels.append("spam-low-value")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_financial_account_message(text, sender, gmail_label_ids):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._is_trusted_personal_sender(sender_email):
            labels.append("personal")
            confidence_band = "medium"
        elif self._looks_like_google_drive_personal_share(text, sender):
            labels.append("personal")
            confidence_band = "medium"
        elif self._looks_like_order_message(header_text, text, sender):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_promotional_message(text, gmail_label_ids, list_unsubscribe, precedence):
            if self._looks_like_requested_promo_message(text):
                labels.append("promotions")
            else:
                labels.append("spam-low-value")
                near_misses.append("promotions")
            confidence_band = "medium"
        elif self._looks_like_bulk_update_message(text, sender, gmail_label_ids, list_unsubscribe, precedence):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif "newsletter" in text or "weekend reads" in text:
            labels.extend(["newsletter", "promotions", "travel", "personal"])
            confidence_band = "low"
        elif self._looks_like_linkedin_direct_message(text, sender, gmail_label_ids):
            labels.append("personal")
            confidence_band = "medium"
        elif self._looks_like_social_low_value_message(text, sender, gmail_label_ids, list_unsubscribe):
            labels.append("spam-low-value")
            near_misses.append("personal")
            confidence_band = "medium"

        return self._normalize_item(
            {
                "source": message.get("source"),
                "account_id": message.get("account_id"),
                "message_id": message["message_id"],
                "sender": message["sender"],
                "subject": message["subject"],
                "date": message["date"],
                "snippet": message.get("snippet"),
                "body": message.get("body"),
                "interpretation": self._interpretation_for(text, sender, gmail_label_ids),
                "applied_labels": labels,
                "near_misses": near_misses,
                "confidence_band": confidence_band,
            }
        )

    def _interpretation_for(self, text: str, sender: str, gmail_label_ids: set[str]) -> str:
        if (
            "travel itinerary" in text
            and "receipt" in text
            and "calendar" in text
            and "personal" in text
        ):
            return "Travel message combining itinerary, receipt, and calendar details."
        if self._looks_like_job_application_message(text, sender):
            return "Job application or interview process update that should stay easy to retrieve."
        if self._looks_like_job_alert_message(text, sender):
            return "Job alert or role recommendation that should stay easy to retrieve while job-searching."
        if self._looks_like_google_play_receipt(text, sender):
            return "Digital purchase or subscription receipt that should stay easy to retrieve with other order records."
        if self._looks_like_requested_promo_message(text):
            return "Solicited wishlist or price-drop reminder that is promotional but still expected."
        if self._looks_like_reply_needed_text(text) and not self._looks_like_legal_notice(text, sender):
            return "Work request that likely needs a response."
        if self._looks_like_account_message(text, sender, gmail_label_ids):
            if "dokument" in text or "document" in text:
                return "Account-related document delivery that likely belongs with other account notices."
            return "Account security or account-access alert that likely needs to stay easy to find."
        if self._looks_like_financial_account_message(text, sender, gmail_label_ids):
            return "Financial account update or statement that is mainly useful for later retrieval."
        if self._looks_like_payment_scam_message(text, sender, gmail_label_ids, "", ""):
            return "Suspicious payment or transaction alert that looks more like low-value scam noise than a useful record."
        if self._is_trusted_personal_sender(normalized_sender_email(sender)):
            return "Direct message from a previously trusted personal sender."
        if self._looks_like_google_drive_personal_share(text, sender):
            return "Person-to-person file or folder share that likely belongs in personal retrieval."
        if self._looks_like_order_message(text, text, sender):
            return "Shipping confirmation for a recent online purchase."
        if self._looks_like_promotional_text(text):
            return "Promotional marketing email that looks low priority to review."
        if "newsletter" in text or "weekend reads" in text:
            return "General newsletter roundup with offers."
        if self._looks_like_linkedin_direct_message(text, sender, gmail_label_ids):
            return "Direct person-to-person social message that likely belongs in personal retrieval."
        if "linkedin" in text:
            return "Social notification that looks low priority unless you are actively tracking it."
        if "terms of service" in text or "policy" in text:
            return "Service update email that looks informational rather than action-worthy."
        return "Informational message with no confident category."

    def _looks_like_promotional_message(
        self,
        text: str,
        gmail_label_ids: set[str],
        list_unsubscribe: str,
        precedence: str,
    ) -> bool:
        if "category_promotions" in gmail_label_ids:
            return True
        return self._looks_like_promotional_text(text) and self._has_bulk_signal(
            gmail_label_ids,
            list_unsubscribe,
            precedence,
        )

    def _is_trusted_personal_sender(self, sender_email: str | None) -> bool:
        return sender_email in self._trusted_personal_senders

    def _looks_like_reply_needed_text(self, text: str) -> bool:
        return (
            "approval" in text
            or "please reply" in text
            or "reply today" in text
            or "needs your response" in text
            or "respond by" in text
        )

    def _looks_like_job_application_message(self, text: str, sender: str) -> bool:
        job_tokens = (
            "job application",
            "your application",
            "application status",
            "application update",
            "thanks for applying",
            "thank you for applying",
            "interview",
            "recruiter",
            "candidate",
            "workday",
            "greenhouse",
            "lever.co",
            "smartrecruiters",
        )
        return any(token in text or token in sender for token in job_tokens)

    def _looks_like_job_alert_message(self, text: str, sender: str) -> bool:
        if "linkedin job alerts" in sender:
            return True
        if "jobalerts-noreply@linkedin.com" in sender:
            return True
        if "jobs-noreply@linkedin.com" in sender and (
            "saved job is expiring" in text or "job’s expiring" in text or "job's expiring" in text
        ):
            return True
        if "linkedin job alerts" not in text:
            return False
        return any(
            token in text
            for token in (
                " at ",
                " is hiring",
                "see job details",
                "apply on linkedin",
                "jobs like this",
            )
        )

    def _looks_like_google_play_receipt(self, text: str, sender: str) -> bool:
        if "googleplay-noreply@google.com" not in sender and "google play" not in sender:
            return False
        return any(
            token in text
            for token in (
                "order receipt",
                "you've been charged",
                "you've been billed",
                "manage your subscriptions",
                "google commerce limited",
                "thank you",
            )
        )

    def _looks_like_legal_notice(self, text: str, sender: str) -> bool:
        return any(
            token in text or token in sender
            for token in (
                "class action",
                "settlement approval hearing",
                "settlement notice",
                "legal notice",
                "avis d'audience",
                "avis d'action collective",
            )
        )

    def _looks_like_account_message(self, text: str, sender: str, gmail_label_ids: set[str]) -> bool:
        if (
            "sign-in" in text
            or "secure your account" in text
            or "password reset" in text
            or "reset password" in text
            or "single-use code" in text
            or "verification code" in text
            or "one-time code" in text
            or ("new password" in text and "account" in text)
        ):
            return True

        if "accounts.google.com" in sender and (
            "security alert" in text
            or "google account" in text
            or "access to some of your google account data" in text
        ):
            return True

        if "category_updates" in gmail_label_ids and (
            ("dokument" in text and ("kliencie" in text or "dyspozycji" in text or "pesel" in text))
            or ("document" in text and "account" in text)
        ):
            return True

        return False

    def _looks_like_financial_account_message(self, text: str, sender: str, gmail_label_ids: set[str]) -> bool:
        finance_sender = any(token in sender for token in ("sun life", "mbna", "n26"))
        statement_text = (
            "statement is ready" in text
            or "estatement is available" in text
            or "investment statement" in text
            or "account statement" in text
            or "kontoauszug" in text
            or "karte belastet" in text
            or "card charged" in text
            or "neue transaktion" in text
            or "new transaction" in text
            or ("beneficiary" in text and finance_sender)
        )
        if finance_sender and statement_text:
            return True
        return "n26" in sender

    def _looks_like_payment_scam_message(
        self,
        text: str,
        sender: str,
        gmail_label_ids: set[str],
        list_unsubscribe: str,
        precedence: str,
    ) -> bool:
        if "n26" in sender or "mbna" in sender or "sun life" in sender:
            return False
        payment_alert_text = (
            "transakcja płatnicza" in text
            or "transakcja platnicza" in text
            or "payment transaction" in text
            or "p24-" in text
            or "przelewy24" in text
        )
        suspicious_text = (
            "kliknij link" in text
            or "click the link" in text
            or "potwierdzenie" in text
            or "confirm payment" in text
            or "pilnie" in text
            or "urgent" in text
        )
        return payment_alert_text and (
            suspicious_text or self._has_bulk_signal(gmail_label_ids, list_unsubscribe, precedence)
        )

    def _looks_like_order_message(self, header_text: str, text: str, sender: str) -> bool:
        commerce_sender = any(token in sender for token in ("amazon", "ebay", "shop", "store", "order"))
        subject_or_snippet_signal = any(
            token in header_text
            for token in (
                "your order",
                "order confirmation",
                "ordered",
                "delivery confirmation",
                "delivered",
                "out for delivery",
                "dispatch",
                "dispatched",
                "shipment",
                "tracking number",
                "track your package",
                "bestellung",
                "bestellbestätigung",
                "versandt",
                "wurde zugestellt",
                "zugestellt",
                "lieferung",
            )
        )
        body_signal = any(
            token in text
            for token in (
                "tracking number",
                "track your package",
                "delivery confirmation",
                "package was delivered",
                "sendungsverfolgung",
                "zustellung",
                "paket wurde zugestellt",
            )
        )
        return subject_or_snippet_signal and (commerce_sender or body_signal)

    def _looks_like_linkedin_direct_message(self, text: str, sender: str, gmail_label_ids: set[str]) -> bool:
        if "category_social" not in gmail_label_ids:
            return False
        if "linkedin" not in sender:
            return False
        return "via linkedin" in sender or "just messaged you" in text or "new message awaits your response" in text

    def _looks_like_social_low_value_message(
        self,
        text: str,
        sender: str,
        gmail_label_ids: set[str],
        list_unsubscribe: str,
    ) -> bool:
        if self._looks_like_linkedin_direct_message(text, sender, gmail_label_ids):
            return False
        if "category_social" not in gmail_label_ids:
            return False
        if not list_unsubscribe:
            return False
        return "linkedin" in sender or "follow" in text or "add " in text or "your first puzzle" in text

    def _looks_like_google_drive_personal_share(self, text: str, sender: str) -> bool:
        if "via google drive" not in sender and "via google sheets" not in sender:
            return False
        if "shared with you" not in text and "shared a" not in text:
            return False
        if "drive-shares-dm-noreply@google.com" not in sender and "google.com" not in sender:
            return False
        return True

    def _looks_like_bulk_update_message(
        self,
        text: str,
        sender: str,
        gmail_label_ids: set[str],
        list_unsubscribe: str,
        precedence: str,
    ) -> bool:
        if "terms of service" in text or "update our terms" in text:
            return True
        if self._looks_like_low_value_digest_or_reminder(text, sender):
            return True
        if "category_updates" not in gmail_label_ids:
            return False
        return self._has_bulk_signal(gmail_label_ids, list_unsubscribe, precedence) and (
            "google" in sender or "update" in text or "introducing" in text or "welcome" in text
        )

    def _looks_like_low_value_digest_or_reminder(self, text: str, sender: str) -> bool:
        if "publicationsnews@imf.org" in sender or "imf publications" in text:
            return True
        if "open house" in text and ("rental" in sender or "apartments" in sender or "community" in text):
            return True
        return False

    def _looks_like_promotional_text(self, text: str) -> bool:
        return any(
            token in text
            for token in (
                " sale",
                "sale:",
                "discount",
                "promotional",
                "offer",
                "offers",
                "off",
                "cash back",
                "free shipping",
                "voucher",
                "hurry",
                "supplies last",
                "introducing",
                "invest",
            )
        )

    def _looks_like_requested_promo_message(self, text: str) -> bool:
        return any(
            token in text
            for token in (
                "wishlist",
                "wish list",
                "saved item",
                "price drop",
                "back in stock",
                "notify me",
                "you asked to be notified",
            )
        )

    def _has_bulk_signal(self, gmail_label_ids: set[str], list_unsubscribe: str, precedence: str) -> bool:
        return bool(list_unsubscribe) or precedence == "bulk" or "category_promotions" in gmail_label_ids

    def _sort_key(self, item: dict) -> tuple[int, float]:
        labels = set(item["applied_labels"])

        if "reply-needed" in labels:
            priority = 0
        elif "account-security" in labels:
            priority = 1
        else:
            priority = 2

        timestamp = datetime.fromisoformat(item["date"].replace("Z", "+00:00")).astimezone(UTC)
        return (priority, -timestamp.timestamp())

    def _normalize_item(self, item: dict) -> dict:
        review_item = dict(item)
        applied_labels = list(review_item["applied_labels"])
        near_misses = list(review_item["near_misses"])

        if "newsletter" in applied_labels and "promotions" in applied_labels:
            applied_labels.remove("promotions")
            near_misses.append("promotions")

        if len(applied_labels) > 3:
            overflow = applied_labels[3:]
            applied_labels = applied_labels[:3]
            near_misses.extend(overflow)

        review_item["applied_labels"] = applied_labels
        review_item["near_misses"] = near_misses
        return review_item
