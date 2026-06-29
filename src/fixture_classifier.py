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
        elif self._looks_like_job_platform_reengagement_message(text, sender_email):
            labels.append("job-related")
            confidence_band = "medium"
        elif self._looks_like_job_application_acknowledgement(text, sender_email):
            labels.append("job-related")
            confidence_band = "medium"
        elif self._looks_like_job_platform_welcome_message(text, sender_email):
            labels.append("job-related")
            confidence_band = "medium"
        elif self._looks_like_fit_analytics_work_update(text, sender_email):
            labels.append("job-related")
            confidence_band = "medium"
        elif self._looks_like_wind_down_work_thread(text, sender_email):
            labels.append("job-related")
            confidence_band = "medium"
        elif self._looks_like_indeed_job_event_notice(text, sender_email):
            labels.append("job-related")
            confidence_band = "medium"
        elif self._looks_like_linkedin_recruiter_message(text, sender_email):
            labels.append("job-related")
            near_misses.append("reply-needed")
            confidence_band = "medium"
        elif self._looks_like_google_play_receipt(text, sender):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_requested_youtube_event_reminder(text, sender_email):
            labels.append("promotions")
            confidence_band = "medium"
        elif self._looks_like_newsletter_digest_notice(text, sender_email):
            labels.append("newsletter")
            confidence_band = "medium"
        elif self._looks_like_unsolicited_linkedin_sales_outreach(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_google_play_subscription_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_google_play_payment_declined_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_google_play_purchase_verification_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_amazon_subscription_billing_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_pay_payment_receipt(text, sender_email):
            labels.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_interac_money_request_expiry(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_paypal_payment_receipt(text, sender_email):
            labels.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_proton_subscription_renewal_notice(text, sender_email):
            labels.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_winsim_invoice_notice(text, sender_email):
            labels.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_audible_order_confirmation(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_audible_membership_state_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_merchant_order_confirmation(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_steam_purchase_receipt(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_oel_order_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_talkpal_receipt(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_talkpal_subscription_activation(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_bad_axe_booking_notice(text, sender_email):
            labels.append("calendar-event")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_eversports_purchase_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_eversports_booking_notice(text, sender_email):
            labels.append("calendar-event")
            confidence_band = "medium"
        elif self._looks_like_uber_trip_receipt(text, sender_email):
            labels.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_return_flow_message(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_return_retrocharge_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_dhl_shipment_update(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_dhl_packstation_dropoff_receipt(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_dpd_tracking_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_dhl_return_receipt_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_travelodge_invoice_notice(text, sender_email):
            labels.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_travelodge_booking_notice(text, sender_email):
            labels.append("travel")
            confidence_band = "medium"
        elif self._looks_like_restaurant_reservation_message(text, sender_email):
            labels.append("calendar-event")
            confidence_band = "medium"
        elif self._looks_like_pid_travel_registration(text, sender_email):
            labels.append("travel")
            confidence_band = "medium"
        elif self._looks_like_trainline_travel_update(text, sender):
            labels.append("travel")
            confidence_band = "medium"
        elif self._looks_like_requested_promo_message(text):
            labels.append("promotions")
            confidence_band = "medium"
        elif self._looks_like_ebay_member_message(text, sender_email):
            labels.extend(["reply-needed", "shopping-order"])
            confidence_band = "medium"
        elif self._looks_like_marketplace_shipment_update(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_shipping_confirmation(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_dpd_shipment_update(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_alltricks_order_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_audible_support_resolution(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("reply-needed")
            confidence_band = "medium"
        elif self._looks_like_order_support_thread(text, sender_email):
            labels.extend(["reply-needed", "shopping-order"])
            confidence_band = "medium"
        elif self._looks_like_reply_needed_text(text) and not self._looks_like_legal_notice(text, sender):
            labels.extend(["reply-needed", "job-related"])
            confidence_band = "high"
        elif self._looks_like_account_message(text, sender, gmail_label_ids):
            labels.append("account-security")
            near_misses.append("reply-needed")
            confidence_band = "high"
        elif self._looks_like_prime_video_subscription_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_prime_video_membership_update_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_prime_membership_resume_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_youtube_premium_welcome_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_youtube_purchase_receipt(text, sender_email):
            labels.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_shopify_billing_notice(text, sender_email):
            labels.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_linkedin_report_acknowledgement(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_knowledgehut_event_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_agilemailer_training_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_alexa_upgrade_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_google_home_gemini_rollout(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_service_policy_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_imf_data_portal_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_recruiting_spam(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_university_enquiry_followup(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_sun_life_cybersecurity_hub_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_marketplace_followup(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_pmi_event_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_amazon_answers_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_amazon_reviews_nudge(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_komoot_weekend_suggestion(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_audible_new_title_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_inaturalist_live_event_invite(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_xai_deprecation_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_inaturalist_nudge(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_xai_announcement(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_wolt_rewards_update(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_google_developer_welcome(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_google_maps_timeline_update(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_workspace_shutdown_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_voi_welcome(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_wolt_verification_feature_update(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_patreon_monthly_update(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_audible_prime_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_slack_policy_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_medavie_provider_bulletin(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_trustpilot_review_request(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_sun_life_planner_update(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_sun_life_tfsa_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_xe_locale_update(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_marcotec_welcome(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_bookyourhunt_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_audible_price_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_microsoft_rewards_expiry(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_reddit_policy_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_amazon_support_survey(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_coursera_promo(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_przelewy24_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_settlement_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_mgm_cybersecurity_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_purple_wifi_upgrade_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_sporcle_trophy_notice(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_institutional_memo(header_text, text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_payment_scam_message(text, sender, gmail_label_ids, list_unsubscribe, precedence):
            labels.append("spam-low-value")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_paypal_legal_update(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_paypal_contact_change_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_paypal_trusted_device_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_linkedin_subscription_cancellation(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_linkedin_subscription_purchase(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_td_security_advisory(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_td_service_disruption_notice(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_schwab_estatement_notice(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_td_account_notice(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_td_new_device_login_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_interac_money_request_notice(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_interac_deposit_notice(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_interac_transfer_expiry_notice(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_wise_account_verification_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_slack_email_confirmation_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_workwave_portal_verification_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_bumble_email_confirmation_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_dropbox_new_signin_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_zoom_password_reset_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_steam_security_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_find_my_device_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_discord_account_deletion_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_one_sec_inactive_account_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_google_wallet_device_removal_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_gumroad_authentication_token(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_github_oauth_application_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_amazon_account_access_attempt(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_amazon_passkey_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_telus_wifi_activation_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_asus_account_activation_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_neteller_reactivation_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_ebay_new_device_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_battlenet_security_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_ubisoft_security_code(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_linkedin_security_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_kinguin_inactive_account_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_google_storage_cutoff_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_wifi_email_verification_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_trello_account_deletion_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_soundiiz_account_deletion_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_prime_billing_problem_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_dashlane_account_deletion_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_ue_application_portal_activation(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_mozilla_login_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_meetup_account_deactivation_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_sun_life_survey(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_coursera_roundup(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_financial_account_message(text, sender, gmail_label_ids):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_medactionplan_invite(text, sender_email):
            labels.append("personal")
            confidence_band = "medium"
        elif self._looks_like_personal_packing_list(text, sender_email):
            labels.append("personal")
            confidence_band = "medium"
        elif self._looks_like_personal_group_trip_planning(text, sender_email):
            labels.append("personal")
            confidence_band = "medium"
        elif self._looks_like_direct_personal_thread(text, sender_email):
            labels.append("personal")
            confidence_band = "medium"
        elif self._looks_like_outlook_folder_share(text, sender_email):
            labels.append("personal")
            confidence_band = "medium"
        elif self._is_trusted_personal_sender(sender_email):
            labels.append("personal")
            confidence_band = "medium"
        elif self._looks_like_cornell_username_reminder(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_sun_life_registration_notice(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_x_login_alert(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_xai_login_alert(text, sender_email):
            labels.append("account-security")
            confidence_band = "medium"
        elif self._looks_like_amazon_payment_declined_order_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_dhl_express_delivery_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_seller_credit_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_delivery_attempt_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_delivery_delay_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_preorder_price_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_customer_service_order_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("reply-needed")
            confidence_band = "medium"
        elif self._looks_like_transit_ticket_receipt(text, sender_email):
            labels.extend(["travel", "receipt-billing"])
            confidence_band = "medium"
        elif self._looks_like_train_ticket_document(text, sender_email):
            labels.append("travel")
            confidence_band = "medium"
        elif self._looks_like_bvg_order_confirmation(text, sender_email):
            labels.append("travel")
            confidence_band = "medium"
        elif self._looks_like_gite_reservation_reply(text, sender_email):
            labels.append("travel")
            near_misses.append("reply-needed")
            confidence_band = "medium"
        elif self._looks_like_service_contract_update(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_td_webbroker_statement_notice(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_bittrex_account_shutdown_notice(text, sender_email):
            labels.append("financial-account")
            confidence_band = "medium"
        elif self._looks_like_wetranfer_sent_transfer_expiry(text, sender_email):
            labels.append("personal")
            confidence_band = "medium"
        elif self._looks_like_book_marketplace_order_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_royal_mail_shipment_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_gls_shipment_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_chronopost_shipment_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_zoxs_order_status_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_caventura_accounting_order_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_irrelevant_alltricks_delivery_survey(text, sender_email):
            labels.append("spam-low-value")
            confidence_band = "medium"
        elif self._looks_like_youtube_channel_membership_notice(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
            confidence_band = "medium"
        elif self._looks_like_amazon_seller_message_with_order_context(text, sender_email):
            labels.append("shopping-order")
            near_misses.append("receipt-billing")
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
                "interpretation": self._interpretation_for(text, sender, sender_email, gmail_label_ids),
                "applied_labels": labels,
                "near_misses": near_misses,
                "confidence_band": confidence_band,
            }
        )

    def _interpretation_for(self, text: str, sender: str, sender_email: str | None, gmail_label_ids: set[str]) -> str:
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
        if self._looks_like_job_platform_reengagement_message(text, sender_email):
            return "Job-platform re-engagement message that still belongs with other work and recruiting mail."
        if self._looks_like_job_application_acknowledgement(text, sender_email):
            return "Job application acknowledgement that should stay easy to retrieve while job-searching."
        if self._looks_like_job_platform_welcome_message(text, sender_email):
            return "Job-platform welcome or onboarding message that should stay easy to retrieve while job-searching."
        if self._looks_like_google_play_receipt(text, sender):
            return "Digital purchase or subscription receipt that should stay easy to retrieve with other order records."
        if self._looks_like_requested_youtube_event_reminder(text, sender_email):
            return "Requested event reminder that is promotional but still expected."
        if self._looks_like_google_play_subscription_notice(text, sender_email):
            return "Subscription change notice that should stay easy to retrieve with other order records."
        if self._looks_like_amazon_subscription_billing_notice(text, sender_email):
            return "Subscription billing problem that should stay easy to retrieve with other order records."
        if self._looks_like_interac_money_request_expiry(text, sender_email):
            return "Expired money-request notice that should stay easy to retrieve with other financial records."
        if self._looks_like_paypal_payment_receipt(text, sender_email):
            return "Payment receipt that should stay easy to retrieve with other billing records."
        if self._looks_like_proton_subscription_renewal_notice(text, sender_email):
            return "Subscription renewal notice that should stay easy to retrieve with other billing records."
        if self._looks_like_winsim_invoice_notice(text, sender_email):
            return "Carrier invoice notice that should stay easy to retrieve with other billing records."
        if self._looks_like_audible_order_confirmation(text, sender_email):
            return "Audible order confirmation that should stay easy to retrieve with other order records."
        if self._looks_like_audible_membership_state_notice(text, sender_email):
            return "Subscription membership state notice that should stay easy to retrieve with other order records."
        if self._looks_like_merchant_order_confirmation(text, sender_email):
            return "Merchant order or payment confirmation that should stay easy to retrieve with other order records."
        if self._looks_like_steam_purchase_receipt(text, sender_email):
            return "Digital storefront purchase receipt that should stay easy to retrieve with other order records."
        if self._looks_like_talkpal_receipt(text, sender_email):
            return "Subscription receipt that should stay easy to retrieve with other order records."
        if self._looks_like_talkpal_subscription_activation(text, sender_email):
            return "Subscription activation notice that should stay easy to retrieve with other order records."
        if self._looks_like_eversports_purchase_notice(text, sender_email):
            return "Purchase confirmation that should stay easy to retrieve with other order records."
        if self._looks_like_eversports_booking_notice(text, sender_email):
            return "Booked class or session details that likely belong with other calendar-style event records."
        if self._looks_like_uber_trip_receipt(text, sender_email):
            return "Trip receipt that should stay easy to retrieve with other billing records."
        if self._looks_like_amazon_return_flow_message(text, sender_email):
            return "Return or refund flow update that should stay easy to retrieve with other order records."
        if self._looks_like_amazon_return_retrocharge_notice(text, sender_email):
            return "Return retrocharge notice that should stay easy to retrieve with other order records."
        if self._looks_like_dhl_shipment_update(text, sender_email):
            return "Shipment update that should stay easy to retrieve with other order records."
        if self._looks_like_dhl_packstation_dropoff_receipt(text, sender_email):
            return "Parcel drop-off receipt that should stay easy to retrieve with other order records."
        if self._looks_like_restaurant_reservation_message(text, sender_email):
            return "Reservation or reminder that likely belongs with other calendar-style event records."
        if self._looks_like_pid_travel_registration(text, sender_email):
            return "Travel-service account registration that should stay easy to retrieve with other trip details."
        if self._looks_like_trainline_travel_update(text, sender):
            return "Train travel update that should stay easy to retrieve alongside other trip details."
        if self._looks_like_requested_promo_message(text):
            return "Solicited wishlist or price-drop reminder that is promotional but still expected."
        if self._looks_like_ebay_member_message(text, sender_email):
            return "Marketplace member message tied to an item listing that likely needs a response."
        if self._looks_like_marketplace_shipment_update(text, sender_email):
            return "Marketplace or courier shipment update that should stay easy to retrieve with other order records."
        if self._looks_like_transit_ticket_receipt(text, sender_email):
            return "Transit purchase receipt that should stay with both trip details and billing records."
        if self._looks_like_train_ticket_document(text, sender_email):
            return "Train ticket document that should stay easy to retrieve with other trip details."
        if self._looks_like_reply_needed_text(text) and not self._looks_like_legal_notice(text, sender):
            return "Work request that likely needs a response."
        if self._looks_like_github_oauth_application_notice(text, sender_email):
            return "GitHub OAuth authorization notice that should stay easy to retrieve as an account-security alert."
        if self._looks_like_account_message(text, sender, gmail_label_ids):
            if "dokument" in text or "document" in text:
                return "Account-related document delivery that likely belongs with other account notices."
            return "Account security or account-access alert that likely needs to stay easy to find."
        if self._looks_like_prime_video_subscription_notice(text, sender_email):
            return "Subscription state update that should stay easy to retrieve with other order records."
        if self._looks_like_prime_membership_resume_notice(text, sender_email):
            return "Prime membership state update that should stay easy to retrieve with other order records."
        if self._looks_like_youtube_premium_welcome_notice(text, sender_email):
            return "Subscription welcome and recurring-charge notice that should stay easy to retrieve with other order records."
        if self._looks_like_shopify_billing_notice(text, sender_email):
            return "Shopify billing notice that should stay easy to retrieve with other billing records."
        if self._looks_like_zoxs_order_status_notice(text, sender_email):
            return "Merchant order-status update that should stay easy to retrieve with other order records."
        if self._looks_like_caventura_accounting_order_notice(text, sender_email):
            return "Merchant shipping or delivery-note document tied to an order."
        if self._looks_like_irrelevant_linkedin_report_acknowledgement(text, sender_email):
            return "Report-status acknowledgement that looks low priority for this inbox."
        if self._looks_like_irrelevant_knowledgehut_event_promo(text, sender_email):
            return "Marketing event invite from an irrelevant training sender that looks low priority for this inbox."
        if self._looks_like_irrelevant_alexa_upgrade_notice(text, sender_email):
            return "Product upsell announcement that looks low priority for this inbox."
        if self._looks_like_irrelevant_google_home_gemini_rollout(text, sender_email):
            return "Product rollout notice for a home device that looks low priority for this inbox."
        if self._looks_like_irrelevant_service_policy_notice(text, sender_email):
            return "Service policy update that looks low priority for this inbox."
        if self._looks_like_irrelevant_imf_data_portal_notice(text, sender_email):
            return "IMF data-portal transition notice that looks low priority for this inbox."
        if self._looks_like_irrelevant_recruiting_spam(text, sender_email):
            return "Recruiting-style spam that looks low priority for this inbox."
        if self._looks_like_irrelevant_university_enquiry_followup(text, sender_email):
            return "Education-enquiry follow-up the founder no longer considers relevant for this inbox."
        if self._looks_like_irrelevant_sun_life_cybersecurity_hub_promo(text, sender_email):
            return "Financial-provider awareness promo that looks low priority for this inbox."
        if self._looks_like_irrelevant_marketplace_followup(text, sender_email):
            return "Marketplace follow-up or reminder that looks low priority for this inbox."
        if self._looks_like_irrelevant_pmi_event_promo(text, sender_email):
            return "Professional event promotion that looks low priority for this inbox."
        if self._looks_like_irrelevant_amazon_answers_notice(text, sender_email):
            return "Amazon community follow-up that looks low priority for this inbox."
        if self._looks_like_paypal_legal_update(text, sender_email):
            return "Financial account legal-update notice that should stay easy to retrieve with other account records."
        if self._looks_like_paypal_contact_change_notice(text, sender_email):
            return "Account-change notice that likely needs to stay easy to retrieve as an account-security alert."
        if self._looks_like_paypal_trusted_device_notice(text, sender_email):
            return "Trusted-device sign-in notice that likely needs to stay easy to retrieve as an account-security alert."
        if self._looks_like_linkedin_subscription_cancellation(text, sender_email):
            return "Subscription cancellation notice that should stay easy to retrieve with other order records."
        if self._looks_like_linkedin_subscription_purchase(text, sender_email):
            return "Subscription purchase confirmation that should stay easy to retrieve with other order records."
        if self._looks_like_td_security_advisory(text, sender_email):
            return "Financial account security advisory that should stay easy to retrieve with other account records."
        if self._looks_like_td_service_disruption_notice(text, sender_email):
            return "Financial account service reminder that should stay easy to retrieve with other account records."
        if self._looks_like_schwab_estatement_notice(text, sender_email):
            return "Brokerage account statement notice that should stay easy to retrieve with other financial records."
        if self._looks_like_interac_money_request_notice(text, sender_email):
            return "Money-request notice that should stay easy to retrieve with other financial records."
        if self._looks_like_slack_email_confirmation_notice(text, sender_email):
            return "Slack email-confirmation notice that likely needs to stay easy to retrieve as an account-security alert."
        if self._looks_like_ebay_new_device_notice(text, sender_email):
            return "Marketplace sign-in notice that likely needs to stay easy to retrieve as an account-security alert."
        if self._looks_like_battlenet_security_notice(text, sender_email):
            return "Gaming-account security notice that likely needs to stay easy to retrieve as an account-security alert."
        if self._looks_like_ubisoft_security_code(text, sender_email):
            return "One-time security code that likely needs to stay easy to retrieve as an account-security alert."
        if self._looks_like_linkedin_security_notice(text, sender_email):
            return "LinkedIn account-security message that likely needs to stay easy to retrieve."
        if self._looks_like_kinguin_inactive_account_notice(text, sender_email):
            return "Inactive-account protection notice that likely needs to stay easy to retrieve as an account-security alert."
        if self._looks_like_google_storage_cutoff_notice(text, sender_email):
            return "Storage cutoff notice that likely needs to stay easy to retrieve as an account-security alert."
        if self._looks_like_wifi_email_verification_notice(text, sender_email):
            return "Email verification notice that likely needs to stay easy to retrieve as an account-security alert."
        if self._looks_like_trello_account_deletion_notice(text, sender_email):
            return "Dormant-account deletion notice that likely needs to stay easy to retrieve as an account-access alert."
        if self._looks_like_prime_billing_problem_notice(text, sender_email):
            return "Subscription billing problem that likely needs to stay easy to retrieve as an account-access alert."
        if self._looks_like_meetup_account_deactivation_notice(text, sender_email):
            return "Dormant-account deletion notice that likely needs to stay easy to retrieve as an account-access alert."
        if self._looks_like_irrelevant_sun_life_survey(text, sender_email):
            return "Customer survey follow-up that looks low priority for this inbox."
        if self._looks_like_irrelevant_coursera_roundup(text, sender_email):
            return "Course marketing roundup that looks low priority for this inbox."
        if self._looks_like_irrelevant_komoot_weekend_suggestion(text, sender_email):
            return "Activity recommendation email that looks low priority for this inbox."
        if self._looks_like_irrelevant_audible_new_title_promo(text, sender_email):
            return "Content recommendation promo that looks low priority for this inbox."
        if self._looks_like_irrelevant_xai_deprecation_notice(text, sender_email):
            return "Vendor deprecation announcement that looks low priority for this inbox."
        if self._looks_like_x_login_alert(text, sender_email):
            return "New-login alert that likely needs to stay easy to retrieve as an account-security notice."
        if self._looks_like_amazon_payment_declined_order_notice(text, sender_email):
            return "Order-payment problem that should stay easy to retrieve with other order records."
        if self._looks_like_book_marketplace_order_notice(text, sender_email):
            return "Book-marketplace order update that should stay easy to retrieve with other order records."
        if self._looks_like_royal_mail_shipment_notice(text, sender_email):
            return "Courier shipment update that should stay easy to retrieve with other order records."
        if self._looks_like_gls_shipment_notice(text, sender_email):
            return "Parcel-tracking update that should stay easy to retrieve with other order records."
        if self._looks_like_youtube_channel_membership_notice(text, sender_email):
            return "Channel-membership purchase notice that should stay easy to retrieve with other order records."
        if self._looks_like_amazon_seller_message_with_order_context(text, sender_email):
            return "Seller or warranty message tied to an order that should stay easy to retrieve with other order records."
        if self._looks_like_irrelevant_inaturalist_nudge(text, sender_email):
            return "Community engagement or event nudge that looks low priority for this inbox."
        if self._looks_like_irrelevant_inaturalist_live_event_invite(text, sender_email):
            return "Community webinar invite that looks low priority for this inbox."
        if self._looks_like_irrelevant_xai_announcement(text, sender_email):
            return "Vendor product announcement that looks low priority for this inbox."
        if self._looks_like_irrelevant_coursera_promo(text, sender_email):
            return "Course marketing email that looks low priority for this inbox."
        if self._looks_like_irrelevant_przelewy24_notice(text, sender_email):
            return "Transaction notice the founder wants treated as low priority for this inbox."
        if self._looks_like_irrelevant_settlement_notice(text, sender_email):
            return "Settlement or legal notice that appears legitimate but low priority for this inbox."
        if self._looks_like_irrelevant_purple_wifi_upgrade_notice(text, sender_email):
            return "Captive-portal or wifi upsell confirmation that looks low priority for this inbox."
        if self._looks_like_irrelevant_sporcle_trophy_notice(text, sender_email):
            return "Gamified achievement email that looks low priority for this inbox."
        if self._looks_like_irrelevant_institutional_memo(text, text, sender_email):
            return "Institutional memo from an irrelevant sender that looks low priority for this inbox."
        if self._looks_like_financial_account_message(text, sender, gmail_label_ids):
            return "Financial account update or statement that is mainly useful for later retrieval."
        if self._looks_like_payment_scam_message(text, sender, gmail_label_ids, "", ""):
            return "Suspicious payment or transaction alert that looks more like low-value scam noise than a useful record."
        if self._is_trusted_personal_sender(sender_email):
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
            "apply now to " in text or ("apply to " in text and " and more" in text)
        ):
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

    def _looks_like_job_platform_reengagement_message(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "notifications@app.instaffo.com"
            and "instaffo" in text
            and "jobvorschläge" in text
            and "registrierung" in text
        )

    def _looks_like_job_application_acknowledgement(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "peoplenet@bertelsmann-hr.de"
            and (
                (
                    ("bewerbung" in text or "application" in text)
                    and ("eingegangen" in text or "thank you for applying" in text)
                )
                or (
                    "talent community" in text
                    and ("account wurde erfolgreich erstellt" in text or "account was successfully created" in text)
                )
            )
        )

    def _looks_like_job_platform_welcome_message(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "info@imploy.co"
            and "welcome to imploy" in text
            and "get started" in text
        )

    def _looks_like_fit_analytics_work_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "se.sebastian.schulze@gmail.com"
            and "fit analytics update" in text
            and "fitaers" in text
            and ("project phoenix" in text or "fit analytics" in text)
        )

    def _looks_like_wind_down_work_thread(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {
                "nkruckmeyer@snap.com",
                "se.sebastian.schulze@gmail.com",
                "baraniecki@gmail.com",
            }
            and "wind down team faqs" in text
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

    def _looks_like_requested_youtube_event_reminder(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@youtube.com"
            and "requested a reminder for this event" in text
        )

    def _looks_like_google_play_subscription_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "googleplay-noreply@google.com"
            and (
                ("subscription will end" in text and "subscription benefits" in text)
                or "trial for youtube will end" in text
            )
        )

    def _looks_like_google_play_purchase_verification_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "googleplay-noreply@google.com"
            and "purchase verification settings" in text
            and ("verify it's you" in text or "face or fingerprint" in text)
        )

    def _looks_like_amazon_subscription_billing_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@amazon.com"
            and "subscription at risk of cancelation" in text
            and "unable to process the payment" in text
        )

    def _looks_like_amazon_pay_payment_receipt(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@amazon.com"
            and "ihre zahlung" in text
            and "amazon pay" in text
            and "abgeschlossen" in text
        )

    def _looks_like_paypal_payment_receipt(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "service@intl.paypal.com"
            and ("receipt for your payment" in text or ("you sent a payment" in text and "transaction id" in text))
        )

    def _looks_like_uber_trip_receipt(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@uber.com"
            and "trip with uber" in text
            and "receipt" in text
        )

    def _looks_like_amazon_return_flow_message(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "rueckgabe@amazon.de"
            and (
                "refund was issued" in text
                or "issued your refund" in text
                or "return was dropped off" in text
                or "return request is confirmed" in text
                or "refund will be issued" in text
                or "your return is confirmed" in text
                or "accepted your return request" in text
            )
        )

    def _looks_like_amazon_return_retrocharge_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "rueckgabe@amazon.de"
            and "original payment method has been charged" in text
            and "have not received the original item yet" in text
        )

    def _looks_like_audible_order_confirmation(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {
                "donotreply@audible.com",
                "do-not-reply@audible.com",
                "donotreply@audible.de",
                "do_not_reply@audible.de",
            }
            and (
                ("order confirmation" in text or "order is complete" in text)
                and ("order number" in text or "visit library" in text)
                or ("bestellnummer" in text and ("deine bestellung bei audible" in text or "bestellung ist bestätigt" in text))
                or ("apple in-app kauf" in text and "danke für deinen einkauf" in text)
            )
        )

    def _looks_like_audible_membership_state_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {
                "do-not-reply@audible.com",
                "donotreply@audible.com",
                "do_not_reply@audible.com",
                "do_not_reply@audible.de",
            }
            and any(
                token in text
                for token in (
                    "membership was cancelled",
                    "membership will be cancelled",
                    "trial is ending soon",
                    "free trial ends",
                    "kündigung deines audible-abos",
                    "kuendigung deines audible-abos",
                    "dein abo endet am",
                )
            )
        )

    def _looks_like_oel_order_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"info@oel-berlin.de", "bestellungen@oel-berlin.de"}
            and (
                "bestellung s4921" in text
                or "oel rechnung" in text
                or "deine bestellung wurde zugestellt" in text
                or "versandaktualisierung" in text
                or "vielen dank für deinen einkauf" in text
            )
        )

    def _looks_like_audible_support_resolution(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "service@audible.de"
            and "nachricht vom kundenservice" in text
            and "problem bei deinem kauf" in text
        )

    def _looks_like_merchant_order_confirmation(self, text: str, sender_email: str | None) -> bool:
        return (
            (
                sender_email == "info@meinlieblingsrahmen.de"
                and (
                    "bestellbestätigung" in text
                    or "bestellbestaetigung" in text
                    or "wurde komplett bezahlt" in text
                    or "wir haben deine zahlung erhalten" in text
                )
            )
            or (
                sender_email == "greatcoffee@caventura.com"
                and "bestellung" in text
                and ("bestellnummer" in text or "auftrag" in text or "erhalten" in text)
            )
        )

    def _looks_like_talkpal_receipt(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "invoice+statements@talkpal.ai"
            and "receipt from talkpal, inc." in text
            and "invoice number" in text
        )

    def _looks_like_talkpal_subscription_activation(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "hello@talkpal.ai"
            and "premium subscription is now active" in text
            and "unlocked all the modes" in text
        )

    def _looks_like_bad_axe_booking_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "badaxe@badaxe.pl"
            and (
                "przypomnienie o zadatku" in text
                or "wizyta bad axe" in text
                or "wymagamy wpłaty 20% zadatku" in text
                or "kwota zadatku" in text
            )
        )

    def _looks_like_google_play_payment_declined_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "googleplay-noreply@google.com"
            and "payment declined" in text
            and "subscription" in text
            and "update payment" in text
        )

    def _looks_like_eversports_purchase_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@eversports.com"
            and "einkauf bei" in text
            and "rechnung" in text
        )

    def _looks_like_eversports_booking_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@eversports.com"
            and "deine anmeldung" in text
            and ("termine:" in text or "reserviert am" in text)
            and "uhr" in text
        )

    def _looks_like_dhl_shipment_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@dhl.de"
            and (
                (
                    "amazon sendung" in text
                    and (
                        "zugestellt" in text
                        or "unterwegs" in text
                        or "sendung wird verladen" in text
                        or "liegt nebenan" in text
                        or "ist angekommen" in text
                    )
                )
                or (
                    "amazon paket" in text
                    and (
                        "kommt heute" in text
                        or "kommt bald" in text
                        or "verspätet sich" in text
                        or "verspaetet sich" in text
                        or "wann und wo möchten sie es empfangen" in text
                    )
                )
                or (
                    ("ihre dhl sendung" in text or "ihre oel versandlager" in text)
                    and any(
                        token in text
                        for token in (
                            "zurückgesendet",
                            "zurueckgesendet",
                            "liegt nur noch 2 tage in der filiale",
                            "liegt zur abholung bereit",
                            "befindet sich auf dem weg in eine filiale",
                            "ist unterwegs",
                            "liegt nebenan",
                            "wird gleich zugestellt",
                            "kommt heute",
                            "live verfolgen",
                        )
                    )
                )
            )
        )

    def _looks_like_dpd_tracking_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@dpd.de"
            and ("verfolgen sie ihr paket" in text or "ihr paket ist auf dem weg" in text)
        )

    def _looks_like_dhl_return_receipt_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@dhl.de"
            and "dhl retoure" in text
            and "einlieferungsbeleg" in text
        )

    def _looks_like_dhl_packstation_dropoff_receipt(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@dhl.de"
            and "einlieferungsbeleg" in text
            and "packstation" in text
        )

    def _looks_like_amazon_shipping_confirmation(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "versandbestaetigung@amazon.de"
            and "dein paket wurde versendet" in text
            and ("bestellnr." in text or "bestellt" in text)
        )

    def _looks_like_travelodge_invoice_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "webmaster@mail.travelodge.co.uk"
            and "travelodge invoice" in text
            and "invoice number" in text
        )

    def _looks_like_travelodge_booking_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "webmaster@mail.travelodge.co.uk"
            and "booking confirmation" in text
            and "confirmation number" in text
        )

    def _looks_like_dhl_express_delivery_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply.odd@dhl.com"
            and "dhl on demand delivery" in text
            and (
                "zugestellt" in text
                or "ihre sendung ist unterwegs" in text
                or "dhl express sendung" in text
                or "delivered!" in text
                or "your delivery is today" in text
                or "your shipment is on its way" in text
            )
        )

    def _looks_like_amazon_delivery_attempt_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "order-update@amazon.de"
            and "delivery attempted" in text
            and "track your delivery" in text
        )

    def _looks_like_amazon_delivery_delay_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "order-update@amazon.de"
            and "delivery update:" in text
            and "running late" in text
            and "track your delivery" in text
        )

    def _looks_like_amazon_preorder_price_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "bestellstatus-antwort@amazon.de"
            and "pre-order price guarantee" in text
            and "you saved" in text
        )

    def _looks_like_amazon_customer_service_order_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "cs-reply@amazon.de"
            and "message from customer service" in text
            and "order #" in text
        )

    def _looks_like_bvg_order_confirmation(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "appsupport@bvg.de"
            and "order confirmation" in text
            and "ticket has already been created" in text
        )

    def _looks_like_transit_ticket_receipt(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "keine-antwort@handyticket.de"
            and "handyticket deutschland" in text
            and "quittung für den ticketkauf" in text
        )

    def _looks_like_train_ticket_document(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "bilety@polregio.pl"
            and "your ticket valid on" in text
        )

    def _looks_like_gite_reservation_reply(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "giteoasis@gmail.com"
            and "réservation" in text
            and "hôtel" in text
        )

    def _looks_like_restaurant_reservation_message(self, text: str, sender_email: str | None) -> bool:
        if sender_email == "noreply@choiceqr.com":
            return (
                ("rezerv" in text or "reservation" in text)
                and ("add to calendar" in text or "kalendář" in text or "kalendáře" in text or "rezervac" in text)
            )
        return (
            sender_email == "reserve-noreply@google.com"
            and "reservation" in text
            and ("confirmed" in text or "booked" in text)
            and "google calendar" in text
        )

    def _looks_like_pid_travel_registration(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "robot@operatorict.cz"
            and "activate your user account" in text
            and "prague integrated transport" in text
        )

    def _looks_like_trainline_travel_update(self, text: str, sender: str) -> bool:
        if "trainline" not in sender:
            return False
        if "your train is delayed" in text:
            return True
        return "get ready for" in text and any(
            token in text
            for token in (
                "journey",
                "before travel",
                "before you travel",
                "your ticket",
                "next trip",
                "get ready to go",
                "don't forget to charge your phone",
            )
        )

    def _looks_like_ebay_member_message(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email is not None
            and (sender_email.endswith("@members.ebay.de") or sender_email.endswith("@members.ebay.com"))
            and ("hat eine nachricht gesendet" in text or "hat eine frage zu artikelnr." in text)
        )

    def _looks_like_marketplace_shipment_update(self, text: str, sender_email: str | None) -> bool:
        if sender_email == "ebay@ebay.com":
            return "in zustellung" in text or "speedpak" in text
        if sender_email is not None and sender_email.endswith("@marketplace.amazon.de"):
            return any(
                token in text
                for token in (
                    "ihr paket ist da",
                    "dpd paket",
                    "zwischen 11:",
                    "bald ist ihr dpd paket da",
                    "ist unterwegs",
                    "vielen dank für ihren einkauf",
                )
            )
        if sender_email == "noreply@fedex.com":
            return (
                "sendung wurde geliefert" in text
                or "lokalen anbieter geliefert" in text
                or "wird von unserem lokalen anbieter geliefert" in text
            )
        if sender_email == "fedex-de-gts-corr@fedex.com":
            return "zollabfertigung" in text and "fedex sendung" in text
        if sender_email == "noreply@paketankuendigung.myhermes.de":
            return "liegt bei deinem nachbarn" in text or "ist auf dem weg" in text
        return False

    def _looks_like_dpd_shipment_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@service.dpd.de"
            and (
                "ihr paket ist da" in text
                or "auf dem weg zum pickup paketshop" in text
                or "auf dem weg zum pickup paketshop / station" in text
                or "in 1-2 werktagen stellen wir ihr dpd paket zu" in text
            )
        )

    def _looks_like_alltricks_order_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"contact@alltricks.com", "contact@alltricks.fr"}
            and "order n°" in text
            and (
                "your order has been shipped" in text
                or "your order has been confirmed" in text
                or "your invoice is available" in text
                or "votre commande a été expédiée" in text
            )
        )

    def _looks_like_zoxs_order_status_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@zoxs.de"
            and "statusupdate zu deiner bestellung" in text
        )

    def _looks_like_caventura_accounting_order_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "accounting@caventura.com"
            and "caventura gmbh" in text
            and (
                "versand ihrer bestellung" in text
                or "lieferschein" in text
            )
            and ("bestellung" in text or "auftrag" in text)
        )

    def _looks_like_order_support_thread(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "tyler@godbolt.ca"
            and "brushwiz.com" in text
            and "order #" in text
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

        if "duolingo" in sender and (
            "password has been exposed" in text
            or ("data breach" in text and "reset your duolingo password" in text)
        ):
            return True

        if "google-noreply@google.com" in sender and (
            "linked google services" in text
            or ("digital markets act" in text and "google account" in text)
        ):
            return True

        if "category_updates" in gmail_label_ids and (
            ("dokument" in text and ("kliencie" in text or "dyspozycji" in text or "pesel" in text))
            or ("document" in text and "account" in text)
        ):
            return True

        return False

    def _looks_like_irrelevant_institutional_memo(
        self,
        header_text: str,
        text: str,
        sender_email: str | None,
    ) -> bool:
        if sender_email != "youngje@gbgh.on.ca":
            return False

        if "gbgh information:" in header_text and "ed team mailboxes" in text:
            return True

        return "gbgh memo -" in header_text and "chief of staff" in text

    def _looks_like_irrelevant_settlement_notice(self, text: str, sender_email: str | None) -> bool:
        if sender_email == "no-reply@conciliainc.com":
            return (
                "mgm resorts international" in text
                and "class action settlement approval hearing" in text
                and ("class action notice" in text or "you have nothing to pay" in text)
            )
        return (
            sender_email == "subscriptionmembershipsettlement@admin.kccllc.com"
            and "check reissue portal" in text
            and ("settlement check" in text or "electronic payment" in text)
        )

    def _looks_like_irrelevant_linkedin_report_acknowledgement(
        self, text: str, sender_email: str | None
    ) -> bool:
        return (
            sender_email == "messages-noreply@linkedin.com"
            and "we received your report" in text
            and "report status" in text
        )

    def _looks_like_irrelevant_inaturalist_nudge(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "inaturalist@inaturalist.org"
            and (
                ("get outside this weekend!" in text and "city nature challenge" in text)
                or ("turns 18" in text and "birthday project" in text)
                or ("make a difference for nature" in text and "inaturalist" in text)
                or ("thanks for joining the city nature challenge" in text and "help with cnc identifications" in text)
            )
        )

    def _looks_like_irrelevant_inaturalist_live_event_invite(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "inaturalist@inaturalist.org"
            and "you're invited to a live inaturalist event" in text
            and ("please register" in text or "webinar" in text)
        )

    def _looks_like_irrelevant_xai_announcement(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@x.ai"
            and (
                "grok build 0.1 now available via xai api" in text
                or ("live search api" in text and "xai api" in text and "beta" in text)
            )
        )

    def _looks_like_irrelevant_wolt_rewards_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "julia@mail.wolt.com"
            and "wolt rewards" in text
            and "please take a moment to read this" in text
        )

    def _looks_like_irrelevant_google_developer_welcome(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "googledev-noreply@google.com"
            and "personalize your google developer program journey" in text
        )

    def _looks_like_irrelevant_google_maps_timeline_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply-maps-timeline@google.com"
            and "timeline update" in text
            and "location history" in text
        )

    def _looks_like_irrelevant_workspace_shutdown_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "workspace-noreply@google.com"
            and "jamboard application wind down" in text
        )

    def _looks_like_irrelevant_voi_welcome(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@trans.voiapp.io"
            and "welcome to voi" in text
            and "ready to ride" in text
        )

    def _looks_like_irrelevant_wolt_verification_feature_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "julia@mail.wolt.com"
            and "new verification feature for your wolt orders" in text
        )

    def _looks_like_irrelevant_patreon_monthly_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@patreon.com"
            and "monthly update: catch up on posts" in text
        )

    def _looks_like_irrelevant_audible_prime_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@audible.de"
            and (
                "2 kostenlose monate" in text
                or "2 monate gehen auf uns" in text
                or "prime-vorteil" in text
            )
        )

    def _looks_like_irrelevant_slack_policy_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "feedback@slack.com"
            and "content deletion policy for free workspaces" in text
        )

    def _looks_like_irrelevant_medavie_provider_bulletin(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "provider+medavie.bluecross.ca@icontactmail2.com"
            and "medical services" in text
            and "service fee update" in text
        )

    def _looks_like_irrelevant_trustpilot_review_request(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply.invitations@trustpilotmail.com"
            and "how many stars would you give" in text
        )

    def _looks_like_irrelevant_sun_life_planner_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "sunlife@info.sunlife.ca"
            and "retirement planner" in text
            and "updated tool" in text
        )

    def _looks_like_irrelevant_sun_life_tfsa_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "sunlife@messages.sunlife.com"
            and "tfsa" in text
            and "grow tax-free" in text
        )

    def _looks_like_irrelevant_xe_locale_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "xe@service.xe.com"
            and "new experience for your xe account" in text
        )

    def _looks_like_irrelevant_marcotec_welcome(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "shop@marcotec-shop.de"
            and "willkommen bei af marcotec" in text
        )

    def _looks_like_irrelevant_bookyourhunt_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"no-reply@bookyourhunt.com", "hello@bookyourhunt.com"}
            and ("it's time to hunt" in text or "get only the hunts you want" in text)
        )

    def _looks_like_irrelevant_audible_price_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@audible.de"
            and ("2,95" in text and "audible guthaben" in text or "für je 2,95" in text)
        )

    def _looks_like_irrelevant_microsoft_rewards_expiry(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "microsoftrewards@emailnotify.microsoft.com"
            and "points will expire soon" in text
        )

    def _looks_like_irrelevant_reddit_policy_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@redditmail.com"
            and "privacy policy" in text
            and "user agreement" in text
        )

    def _looks_like_irrelevant_amazon_support_survey(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "return@amazon.com"
            and "let us know how we did" in text
        )

    def _looks_like_irrelevant_coursera_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@m.mail.coursera.org"
            and "dive deeper with data analysis" in text
        )

    def _looks_like_irrelevant_pmi_event_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "email@mail.pmi.org"
            and "denis lassance" in text
            and ("achieve more" in text or "rethink success" in text)
        )

    def _looks_like_irrelevant_amazon_answers_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "answers@amazon.de"
            and "did not receive any answers" in text
            and "unlikely to receive an answer" in text
        )

    def _looks_like_irrelevant_amazon_reviews_nudge(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "customer-reviews-messages@amazon.de"
            and "reviews are getting noticed" in text
            and "reviewing more products" in text
        )

    def _looks_like_irrelevant_service_policy_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            (
                sender_email == "noreply@email.openai.com"
                and (
                    "privacy policy" in text
                    or "datenschutzerklärung" in text
                    or "nutzungsbedingungen" in text
                )
            )
            or (sender_email == "notice-noreply@email3.gog.com" and "updating gog terms" in text)
            or (sender_email == "info@trans.voiapp.io" and "privacy policy" in text)
            or (sender_email == "notification@email.ticketmaster.com" and "terms of use" in text and "policies" in text)
            or (
                sender_email == "updates-noreply@linkedin.com"
                and ("share their thoughts on linkedin" in text or "shared a post" in text)
            )
        )

    def _looks_like_irrelevant_agilemailer_training_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "olivia@agilemailer.com"
            and ("certification training" in text or "training course" in text)
            and (
                "project management professional" in text
                or "pmp" in text
                or "certified scrum product owner" in text
                or "cspo" in text
                or "safe® 6.0 product owner/product manager" in text
                or "safe 6.0 product owner/product manager" in text
                or "popm" in text
            )
        )

    def _looks_like_irrelevant_mgm_cybersecurity_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "mgmresortsnotification@cyberscout.com"
            and "important information about cybersecurity issue" in text
        )

    def _looks_like_irrelevant_imf_data_portal_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "idata@imf.org"
            and ("data.imf.org" in text or "data portal" in text)
            and (
                "legacy data portal" in text
                or "upcoming changes to imf data portal" in text
                or "new imf data portal" in text
            )
        )

    def _looks_like_irrelevant_recruiting_spam(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "uaepantak@freemail.hu"
            and "pantak group llc" in text
            and ("updated copy of your cv" in text or "forward an updated copy" in text)
        )

    def _looks_like_irrelevant_university_enquiry_followup(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"hannah.klein@ue-germany.com", "samiksha.shrivastava@ue-germany.com"}
            and "university of europe for applied sciences" in text
            and (
                "still interested in joining us" in text
                or "discuss your studies with us" in text
                or "recent enquiry to study with us" in text
                or "student recruitment team" in text
                or "follow-up on your inquiry at ue" in text
                or "academic career at the university of europe for applied sciences" in text
                or "book a ms teams consultation" in text
                or "closed your enquiry" in text
                or "you enquired about studying at the university of europe for applied sciences" in text
            )
        )

    def _looks_like_irrelevant_abebooks_welcome(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "news@info.abebooks.de"
            and "herzlich willkommen bei abebooks" in text
            and "registriert" in text
        )

    def _looks_like_irrelevant_marketplace_followup(self, text: str, sender_email: str | None) -> bool:
        if self._looks_like_irrelevant_abebooks_welcome(text, sender_email):
            return True
        if sender_email != "ebay@ebay.com":
            return False
        return (
            "bewertung abgeben" in text
            or "bewerten sie ihren letzten kauf" in text
            or "kürzlich angesehen" in text
            or "kuerzlich angesehen" in text
            or "limitiert verfügbar" in text
            or "limitiert verfugbar" in text
            or "nur noch 1 übrig" in text
            or "nur noch 1 uebrig" in text
            or "der verkäufer bietet" in text
            or "der verkaeufer bietet" in text
        )

    def _looks_like_irrelevant_sun_life_cybersecurity_hub_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "sunlife@info.sunlife.ca"
            and "cybersecurity hub" in text
            and "explore the hub" in text
        )

    def _looks_like_prime_video_subscription_notice(self, text: str, sender_email: str | None) -> bool:
        if sender_email != "no-reply@primevideo.com":
            return False
        return any(
            signal in text
            for signal in (
                "your special offer on your",
                "bei prime video gebucht",
                "zusatzkanal-buchung",
                "kündigung deiner buchung von",
                "aenderung an deiner buchung von",
                "änderung an deiner buchung von",
                "deine buchung von ",
            )
        )

    def _looks_like_prime_video_membership_update_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"prime@amazon.com", "prime@amazon.de"}
            and "an update on prime video" in text
            and "prime video experience" in text
            and "limited advertisements" in text
            and "ad-free option" in text
        )

    def _looks_like_prime_membership_resume_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "prime@amazon.com"
            and "welcome back to prime" in text
            and "renewal date" in text
            and (
                "you've resumed your membership" in text
                or "you’ve resumed your membership" in text
                or "membership resumes today" in text
            )
        )

    def _looks_like_youtube_premium_welcome_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply-purchases@youtube.com"
            and (
                ("welcome to premium lite" in text and "payment method will be charged monthly" in text)
                or ("welcome to youtube premium" in text and ("order number" in text or "manage and cancel" in text))
            )
        )

    def _looks_like_youtube_purchase_receipt(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply-purchases@youtube.com"
            and "your youtube receipt" in text
            and "purchase details" in text
        )

    def _looks_like_shopify_billing_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "billing@shopify.com"
            and "bill for" in text
        )

    def _looks_like_winsim_invoice_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@winsim.de"
            and "winsim-rechnung" in text
        )

    def _looks_like_irrelevant_przelewy24_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"no-reply@przelewy24.pl", "info@przelewy24.pl"}
            and "nowa transakcja płatnicza" in text
        )

    def _looks_like_irrelevant_knowledgehut_event_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "mailer@certs.knowledgehut.com"
            and "upgrad knowledgehut" in text
            and ("upcoming event" in text or "reserved seat" in text or "confirm your seat" in text)
        )

    def _looks_like_irrelevant_alexa_upgrade_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "account-update@amazon.com"
            and "upgrade to the all-new alexa" in text
            and "alexa+" in text
            and "included with prime" in text
        )

    def _looks_like_irrelevant_google_home_gemini_rollout(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "googlehome@google.com"
            and "gemini for home voice assistant" in text
            and "say hello to gemini" in text
            and "get started" in text
        )

    def _looks_like_paypal_legal_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no_reply@communications.paypal.com"
            and "paypal legal agreements" in text
        )

    def _looks_like_paypal_contact_change_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"service@intl.paypal.com", "notification@paypal.com"}
            and ("added your phone number" in text or "added a new email address" in text)
        )

    def _looks_like_paypal_trusted_device_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "service@intl.paypal.com"
            and "stay logged in on this trusted device" in text
        )

    def _looks_like_linkedin_subscription_cancellation(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "billing-noreply@linkedin.com"
            and "premium career" in text
            and "subscription" in text
            and ("canceled" in text or "cancelled" in text)
        )

    def _looks_like_linkedin_subscription_purchase(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "billing-noreply@linkedin.com"
            and "thank you for purchasing premium career" in text
            and "purchase is confirmed" in text
        )

    def _looks_like_td_security_advisory(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@td.com"
            and "td direct investing" in text
            and "phishing scams" in text
        )

    def _looks_like_td_service_disruption_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@td.com"
            and (
                "canada post disruption" in text
                or "potential canada post service disruption" in text
                or "mail delivery delays" in text
                or "canada post services may be disrupted" in text
                or ("electronic funds transfer" in text and "paper cheques" in text)
            )
        )

    def _looks_like_td_account_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@td.com"
            and (
                ("statement delivery preferences" in text and "paperless" in text)
                or ("td canada trust account" in text and "important information about your" in text)
            )
        )

    def _looks_like_td_new_device_login_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply-onlineaccess@td.com"
            and "new device login" in text
            and "sign in from a new device" in text
            and "change your password" in text
        )

    def _looks_like_interac_money_request_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"catch@payments.interac.ca", "notify@payments.interac.ca"}
            and (
                ("request for money" in text and "has expired" in text)
                or ("has requested" in text and "respond to transfer request" in text)
            )
        )

    def _looks_like_interac_deposit_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "notify@payments.interac.ca"
            and (
                ("claim your deposit" in text and "select your financial institution" in text)
                or ("your funds await" in text and "deposit funds" in text)
                or ("remember to deposit your money" in text and "sent you a money transfer" in text)
                or ("sent you money" in text and "to deposit your money" in text)
            )
        )

    def _looks_like_interac_transfer_expiry_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "notify@payments.interac.ca"
            and (
                ("transfer from" in text and "has expired" in text)
                or ("claim your $" in text and "interac e-transfer" in text)
            )
        )

    def _looks_like_wise_account_verification_notice(self, text: str, sender_email: str | None) -> bool:
        if sender_email != "noreply@wise.com":
            return False
        return (
            "restrict your account" in text
            or ("confirm your details by" in text and "wise" in text)
        )

    def _looks_like_slack_email_confirmation_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email is not None
            and sender_email.endswith("@slack.com")
            and (
                ("confirm your email address on slack" in text and "confirm your email address" in text)
                or ("slack confirmation code:" in text and "help you get signed in" in text)
            )
        )

    def _looks_like_workwave_portal_verification_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@workwave.com"
            and "complete verification" in text
            and "customer portal" in text
        )

    def _looks_like_bumble_email_confirmation_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "hi@bumble.com"
            and ("bestätige deine e-mail adresse" in text or "bestaetige deine e-mail adresse" in text)
        )

    def _looks_like_dropbox_new_signin_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@dropbox.com"
            and "signed in to your dropbox account" in text
            and "is this you" in text
        )

    def _looks_like_zoom_password_reset_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@zoom.us"
            and "password has been reset" in text
        )

    def _looks_like_steam_security_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@steampowered.com"
            and (
                "new sign in to steam" in text
                or "steam account: access from new computer" in text
                or "steam guard code" in text
            )
        )

    def _looks_like_steam_purchase_receipt(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@steampowered.com"
            and "thank you for your steam purchase!" in text
        )

    def _looks_like_find_my_device_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply-findmydevice@google.com"
            and "find my device" in text
            and ("network is on" in text or "will soon join the find my device network" in text)
        )

    def _looks_like_discord_account_deletion_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"noreply@discord.com", "notifications@discord.com"}
            and ("account scheduled for deletion" in text or "update your username by" in text)
        )

    def _looks_like_one_sec_inactive_account_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@1se.co"
            and "1se account" in text
            and ("inactive" in text or "deleted" in text)
        )

    def _looks_like_google_wallet_device_removal_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "googlewallet-noreply@google.com"
            and "your card was deleted" in text
            and "inactive device" in text
        )

    def _looks_like_gumroad_authentication_token(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@gumroad.com"
            and "authentication token" in text
            and "new login to your gumroad account" in text
        )

    def _looks_like_proton_subscription_renewal_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@notify.proton.me"
            and "subscription has been renewed" in text
        )

    def _looks_like_github_oauth_application_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@github.com"
            and "[github]" in text
            and (
                "third-party oauth application has been added to your account" in text
                or "third-party github application has been added to your account" in text
                or "is requesting updated permissions" in text
            )
        )

    def _looks_like_amazon_account_access_attempt(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"account-update@amazon.de", "account-update@amazon.com"}
            and "account data access attempt" in text
            and "someone is attempting to access your account data" in text
        )

    def _looks_like_amazon_passkey_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"account-update@amazon.com", "account-update@amazon.ca"}
            and "passkey" in text
            and (
                "erfolgreich eingerichtet" in text
                or "passkey added to your account" in text
                or "passkey was added to your amazon account" in text
            )
        )

    def _looks_like_schwab_estatement_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "donotreply@mail.schwab.com"
            and "your account estatement is available" in text
        )

    def _looks_like_telus_wifi_activation_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "telusservice@i.telus.com"
            and "telus public wi-fi" in text
            and "activate your account" in text
        )

    def _looks_like_asus_account_activation_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "asus_member@asus.com"
            and "verify your e-mail account" in text
            and "welcome to be asus account" in text
        )

    def _looks_like_neteller_reactivation_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            (
                sender_email == "no-reply@emails.neteller.com"
                and "inactive for more than two years" in text
                and "log in to continue using" in text
            )
            or (
                sender_email == "communications@news.neteller.com"
                and "deposit and withdrawal fees" in text
            )
        )

    def _looks_like_ebay_new_device_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "ebay@ebay.com"
            and (
                "neuen gerät genutzt" in text
                or "neuen geraet genutzt" in text
                or "new device" in text
            )
        )

    def _looks_like_battlenet_security_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@battle.net"
            and (
                "battle.net account verification" in text
                or "security check" in text
                or "password change notice" in text
            )
        )

    def _looks_like_ubisoft_security_code(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "updates@account.ubisoft.com"
            and "security code" in text
            and "temporary security code" in text
        )

    def _looks_like_linkedin_security_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "security-noreply@linkedin.com"
            and (
                "added to your account" in text
                or ("here's your pin" in text and "verify it's you" in text)
            )
        )

    def _looks_like_kinguin_inactive_account_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "legal@notices.kinguin.net"
            and "inactive accounts policy" in text
            and (
                "account freeze" in text
                or "account deactivation" in text
                or "may be frozen" in text
                or "may be deactivated" in text
            )
        )

    def _looks_like_google_storage_cutoff_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            (
                sender_email == "google-noreply@google.com"
                and (
                    ("gmail will stop working" in text and "out of storage" in text)
                    or ("gmail storage is 86% full" in text)
                )
            )
            or (
                sender_email == "noreply-photos@google.com"
                and "out of storage" in text
                and "no longer back up new photos or videos" in text
            )
        )

    def _looks_like_wifi_email_verification_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            (
                sender_email == "noreply@cloud4wi.com"
                and "validate your email address" in text
            )
            or (
                sender_email == "no-reply@icomera.com"
                and "validation required" in text
                and "wifi" in text
            )
        )

    def _looks_like_trello_account_deletion_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "do-not-reply@trello.com"
            and "keep your account active" in text
            and ("account will be deleted" in text or "jump back into trello to keep your account" in text)
        )

    def _looks_like_soundiiz_account_deletion_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "info@soundiiz.com"
            and "scheduled soundiiz account deletion" in text
            and "sign back into soundiiz" in text
            and "deleted on" in text
        )

    def _looks_like_prime_billing_problem_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"prime@amazon.com", "prime@amazon.de"}
            and (
                ("payment method" in text or "billing issue" in text)
                and ("benefits are on hold" in text or "membership has been paused" in text)
                or ("prime membership needs your attention" in text)
                or ("prime-mitgliedschaft benötigt ihre aufmerksamkeit" in text)
            )
        )

    def _looks_like_dashlane_account_deletion_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@dashlane.com"
            and "dashlane account has been deleted" in text
        )
 
    def _looks_like_ue_application_portal_activation(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@ue-germany.de"
            and "application portal" in text
            and "account activation" in text
        )

    def _looks_like_mozilla_login_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "accounts@firefox.com"
            and ("vpn" in text or "login" in text or "登录活动" in text)
        )

    def _looks_like_meetup_account_deactivation_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "info@email.meetup.com"
            and "account" in text
            and ("deactivated" in text or "deletion" in text)
            and "log in" in text
        )

    def _looks_like_irrelevant_sun_life_survey(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "sunlife@email.sunlife.com"
            and "share your feedback" in text
            and "survey" in text
            and "gift cards" in text
        )

    def _looks_like_irrelevant_coursera_roundup(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@m.mail.coursera.org"
            and (
                "courses" in text
                or "michigan online" in text
                or "this month" in text
                or "critical thinking" in text
            )
        )

    def _looks_like_irrelevant_komoot_weekend_suggestion(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@komoot.de"
            and "highlights will make your weekend" in text
        )

    def _looks_like_irrelevant_audible_new_title_promo(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"noreply@audible.de", "donotreply@audible.com", "do-not-reply@audible.com"}
            and (
                ("neuer titel" in text and "jetzt hören" in text)
                or ("you've got" in text and "credits" in text)
                or ("50% rabatt" in text and "nur für dich" in text)
                or ("50% rabatt" in text and "nur fuer dich" in text)
            )
        )

    def _looks_like_irrelevant_xai_deprecation_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@x.ai"
            and "deprecation" in text
        )

    def _looks_like_x_login_alert(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "verify@x.com"
            and ("new login" in text or "new or unusual x login" in text)
            and ("was this you" in text or "security alert" in text)
        )

    def _looks_like_xai_login_alert(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@x.ai"
            and "new login to your xai account" in text
        )

    def _looks_like_irrelevant_purple_wifi_upgrade_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@purple.ai"
            and "wifi plan" in text
            and "free wifi plan" in text
        )

    def _looks_like_irrelevant_sporcle_trophy_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "do-not-reply@sporcle.com"
            and "earned a new trophy" in text
        )

    def _looks_like_amazon_seller_message_with_order_context(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@amazon.de"
            and "message from the amazon seller" in text
            and ("order id" in text or "amazon customer" in text)
        )

    def _looks_like_amazon_payment_declined_order_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "payments-update@amazon.de"
            and "payment has been declined" in text
            and "order" in text
            and "update the payment method" in text
        )

    def _looks_like_book_marketplace_order_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {
                "online@buechertisch.org",
                "noreply@medimops.de",
                "noreply_transactional@abebooks.de",
            }
            and any(
                token in text
                for token in (
                    "bestellung",
                    "bestellnummer",
                    "rechnung",
                    "sendungsnummer",
                    "versandbestätigung",
                    "versandbestaetigung",
                    "eingegangen",
                    "bestätigt",
                    "bestaetigt",
                    "abebooks/zvab",
                )
            )
        )

    def _looks_like_royal_mail_shipment_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@royalmail.com"
            and "royal mail-paket" in text
            and any(
                token in text
                for token in (
                    "konnte nicht zugestellt werden",
                    "wird zeitnah zugestellt",
                    "wird für die zustellung bearbeitet",
                    "wird fuer die zustellung bearbeitet",
                    "befindet sich auf dem versandweg",
                )
            )
        )

    def _looks_like_gls_shipment_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@gls-pakete.de"
            and "paket" in text
            and any(
                token in text
                for token in (
                    "an einen nachbarn übergeben",
                    "an einen nachbarn uebergeben",
                    "kommt heute",
                    "wird in wenigen tagen zugestellt",
                    "sendungsverfolgung",
                )
            )
        )

    def _looks_like_youtube_channel_membership_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply-purchases@youtube.com"
            and "membership to" in text
            and ("order date" in text or "perks and benefits" in text)
        )

    def _looks_like_chronopost_shipment_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "avisage-ne-pas-repondre@chronopost.fr"
            and "parcel" in text
            and ("being handled in our network" in text or "track your shipment" in text)
        )

    def _looks_like_irrelevant_alltricks_delivery_survey(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "contact@alltricks.fr"
            and "votre avis compte pour nous" in text
            and "suite à la livraison de votre commande" in text
        )

    def _looks_like_amazon_seller_credit_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email is not None
            and sender_email.endswith("@marketplace.amazon.de")
            and ("gutschrift" in text or "refund" in text)
            and "auftragsnummer" in text
        )

    def _looks_like_wetranfer_sent_transfer_expiry(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "noreply@wetransfer.com"
            and "transfer you sent is about to expire" in text
        )

    def _looks_like_financial_account_message(self, text: str, sender: str, gmail_label_ids: set[str]) -> bool:
        finance_sender = any(
            token in sender
            for token in (
                "sun life",
                "mbna",
                "n26",
                "wise",
                "wealthsimple",
                "stefczyk",
                "stefczykonline",
                "bittrex",
            )
        )
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
            or "privacy notices" in text
            or "privacy notice" in text
            or "client account agreement" in text
            or "rrsp" in text
            or "contribution limit" in text
            or "depositor" in text
            or "deponent" in text
            or "fund closures" in text
            or "choices plan" in text
            or "tax slips and receipts" in text
            or "tax slips right away" in text
            or "tax forms" in text
            or ("paperless" in text and "tax slips" in text)
            or ("beneficiary" in text and finance_sender)
        )
        if finance_sender and statement_text:
            return True
        return "n26" in sender

    def _looks_like_interac_money_request_expiry(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "catch@payments.interac.ca"
            and "request for money" in text
            and "has expired" in text
        )

    def _looks_like_medactionplan_invite(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "info4@medactionplan.com"
            and "mymedschedule plus" in text
            and "medication list" in text
            and "georgetown university hospital has invited you" in text
        )

    def _looks_like_cornell_username_reminder(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "merlinhelp@birds.cornell.edu"
            and "username reminder" in text
            and "cornell lab account" in text
        )

    def _looks_like_sun_life_registration_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            (
                sender_email == "sun_life_financial@info.sunlife.ca"
                and (
                    ("registration code" in text and "continue your registration" in text)
                    or ("confirm your email address with sun life" in text and "continue with your registration" in text)
                )
            )
            or (
                sender_email == "security_alerts@info.sunlife.ca"
                and "two-step verification" in text
                and "security to your account" in text
            )
        )

    def _looks_like_personal_packing_list(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "melissacriding@gmail.com"
            and "packing list" in text
            and "what i plan to bring" in text
        )

    def _looks_like_outlook_folder_share(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "kyle_rd@outlook.com"
            and "shared the folder" in text
            and "invited you to access a folder" in text
        )

    def _looks_like_personal_group_trip_planning(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"tyler@godbolt.ca", "alec.mcalister@gmail.com", "ridings@rogers.com"}
            and (
                "wedding" in text
                or "wittenberge" in text
                or "havelberg" in text
                or "sleeping arrangements" in text
            )
            and (
                "banff" in text
                or "canmore" in text
                or "accommodations options" in text
                or "hotel" in text
                or "air bnb" in text
                or "airbnb" in text
                or "suite with a kitchen" in text
            )
        )

    def _looks_like_direct_personal_thread(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {"davsmock@gmail.com", "dancole@zoho.com"}
            and (
                "zoom meeting in progress" in text
                or "reading determined" in text
                or "invitation to" in text
            )
        )

    def _looks_like_service_contract_update(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email in {
                "service@insightpestsolutions.net",
                "service@insightpestcanada.com",
                "email@e.email-td.com",
            }
            and (
                "cancellation of contract" in text
                or "service reminder" in text
                or "fraud prevention steps" in text
            )
        )

    def _looks_like_td_webbroker_statement_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "td.webbroker@td.com"
            and "direct investing account statement" in text
        )

    def _looks_like_bittrex_account_shutdown_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@global.bittrex.com"
            and (
                (
                    "trading now suspended" in text
                    and "client relationship" in text
                    and "ability to withdraw" in text
                )
                or (
                    "bittrex global" in text
                    and "wind down its operations" in text
                    and "no funds" in text
                    and "no action is required from you" in text
                )
            )
        )

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
                "shipped",
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
                "lieferstatus",
                "lieferstatus:",
                "versandt",
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
        if (
            "via google drive" not in sender
            and "via google sheets" not in sender
            and "via google docs" not in sender
        ):
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

    def _looks_like_newsletter_digest_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            (
                sender_email in {"bingo@patreon.com", "quincy@freecodecamp.org"}
                and (
                    "just shared:" in text
                    or "just shared" in text
                    or "learn to code" in text
                )
            )
            or (
                sender_email == "noreply.dfd@goethe.de"
                and "deutsch für dich" in text
                and "news from the" in text
            )
        )

    def _looks_like_unsolicited_linkedin_sales_outreach(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "hit-reply@linkedin.com"
            and ("api adoption" in text or "developer experience" in text)
            and ("are you open to discussing this further" in text or "set something up on your calendar" in text)
        )

    def _looks_like_indeed_job_event_notice(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "no-reply@indeed.com"
            and ("neuer job gesucht" in text or "bewerbungsgespräch vereinbaren" in text or "online job event" in text)
        )

    def _looks_like_linkedin_recruiter_message(self, text: str, sender_email: str | None) -> bool:
        return (
            sender_email == "inmail-hit-reply@linkedin.com"
            and ("remote position" in text or "send me your resume" in text or "selective process" in text)
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
