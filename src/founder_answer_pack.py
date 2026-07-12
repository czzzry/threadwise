from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import founder_answer_pack_path, write_json
from src.memory_proposal_store import build_memory_proposal, load_storage_items


ANSWER_LABELS = {
    ("marketing-preference", "low_value_default"): ("promotions", "sender-cluster"),
    ("marketing-preference", "keep_visible"): (None, None),
    ("account-security-handling", "always_visible"): ("account-security", "sender-cluster"),
    ("account-security-handling", "known_service_low_priority"): (None, None),
    ("events-and-confirmations", "calendar_event_default"): ("calendar-event", "sender-cluster"),
    ("events-and-confirmations", "personal_default"): ("personal", "sender-cluster"),
    ("shopping-and-order-confirmations", "shopping_order_default"): ("shopping-order", "sender-cluster"),
    ("shopping-and-order-confirmations", "receipt_billing_default"): ("receipt-billing", "sender-cluster"),
    ("shopping-and-order-confirmations", "calendar_or_personal_default"): ("calendar-event", "sender-cluster"),
    ("personal-vs-low-value", "personal_default"): ("personal", "sender-cluster"),
    ("personal-vs-low-value", "low_value_default"): ("spam-low-value", "sender-cluster"),
    ("direct-message-handling", "personal_default"): ("personal", "sender-cluster"),
    ("direct-message-handling", "sender_allowlist_only"): (None, None),
    ("terms-and-policy-updates", "low_value_update_default"): ("newsletter", "sender-cluster"),
    ("terms-and-policy-updates", "keep_account_related_visible"): (None, None),
    ("taxonomy-gap", "map_existing_label"): (None, None),
    ("taxonomy-gap", "leave_unresolved"): (None, None),
}


def build_founder_answer_pack(
    *,
    founder_question_pack: dict,
    review_pack: dict,
    provider_storage_dirs: list[tuple[str, Path]],
) -> dict:
    storage_dir_by_provider = {provider: path for provider, path in provider_storage_dirs}
    storage_items_by_provider = {
        provider: load_storage_items(path, provider)
        for provider, path in provider_storage_dirs
    }
    review_target_index = {
        (target.get("provider", ""), target.get("sender_key", ""), target.get("subject_key", "")): target
        for target in review_pack.get("top_review_targets", [])
    }

    questions = []
    for question in founder_question_pack.get("questions", []):
        answer_options = []
        for answer in question.get("draft_answers", []):
            label, scope = ANSWER_LABELS.get((question.get("theme", ""), answer.get("answer_key", "")), (None, None))
            proposal_drafts = []
            if label and scope:
                for target_ref in question.get("example_targets", []):
                    review_target = review_target_index.get(
                        (
                            target_ref.get("provider", ""),
                            target_ref.get("sender_key", ""),
                            target_ref.get("subject_key", ""),
                        )
                    )
                    if review_target is None:
                        continue
                    provider = review_target.get("provider", "")
                    examples = list(review_target.get("examples", []))
                    if not examples:
                        continue
                    proposal = build_memory_proposal(
                        provider=provider,
                        account_id=examples[0].get("account_id", ""),
                        source_batch_id=examples[0].get("batch_id", ""),
                        selected_items=examples,
                        scope=scope,
                        label=label,
                        explanation=_proposal_explanation(question, answer, review_target),
                        storage_items=storage_items_by_provider.get(provider, []),
                    )
                    proposal_payload = proposal.to_dict()
                    proposal_payload["preview_match_count"] = proposal.preview.get("match_count", 0)
                    proposal_payload["sender_key"] = review_target.get("sender_key", "")
                    proposal_payload["subject_key"] = review_target.get("subject_key", "")
                    proposal_payload["count"] = review_target.get("count", 0)
                    proposal_drafts.append(proposal_payload)
            answer_options.append(
                {
                    "answer_key": answer.get("answer_key", ""),
                    "description": answer.get("description", ""),
                    "proposal_drafts": proposal_drafts,
                    "projection": _projection_for_answer(question, proposal_drafts),
                }
            )
        questions.append(
            {
                "question_id": question.get("question_id", ""),
                "theme": question.get("theme", ""),
                "title": question.get("title", ""),
                "prompt": question.get("prompt", ""),
                "providers": list(question.get("providers", [])),
                "family_count": question.get("family_count", 0),
                "estimated_unblocked_messages": question.get("estimated_unblocked_messages", 0),
                "answer_options": answer_options,
            }
        )

    return {
        "generated_at": _now_iso(),
        "artifact_type": "founder-answer-pack",
        "summary": {
            "question_count": len(questions),
            "answer_option_count": sum(len(question.get("answer_options", [])) for question in questions),
            "actionable_answer_count": sum(
                1
                for question in questions
                for answer in question.get("answer_options", [])
                if answer.get("projection", {}).get("estimated_resolved_messages", 0) > 0
            ),
        },
        "questions": questions,
    }


def write_founder_answer_pack(
    output_storage_dir: Path,
    *,
    founder_question_pack: dict,
    review_pack: dict,
    provider_storage_dirs: list[tuple[str, Path]],
) -> dict:
    payload = build_founder_answer_pack(
        founder_question_pack=founder_question_pack,
        review_pack=review_pack,
        provider_storage_dirs=provider_storage_dirs,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = founder_answer_pack_path(output_storage_dir, f"founder-answer-pack-{timestamp}")
    write_json(path, payload)
    payload["pack_path"] = str(path)
    return payload


def _proposal_explanation(question: dict, answer: dict, review_target: dict) -> str:
    sender_key = review_target.get("sender_key", "")
    subject_key = review_target.get("subject_key", "")
    return (
        f"Drafted from founder question '{question.get('theme', '')}' with answer "
        f"'{answer.get('answer_key', '')}' for recurring family {sender_key} / {subject_key}."
    )


def _projection_for_answer(question: dict, proposal_drafts: list[dict]) -> dict:
    return {
        "proposal_count": len(proposal_drafts),
        "estimated_resolved_messages": sum(int(draft.get("count", 0)) for draft in proposal_drafts),
        "estimated_unblocked_fraction": _fraction(
            sum(int(draft.get("count", 0)) for draft in proposal_drafts),
            int(question.get("estimated_unblocked_messages", 0)),
        ),
    }


def _fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 2)


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
