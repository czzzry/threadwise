from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.founder_answer_application import apply_founder_answer_decision
from src.founder_answer_pack import ANSWER_LABELS
from src.founder_answer_decision import save_founder_answer_decision
from src.founder_question_pack import QUESTION_THEME_CONFIG, _draft_answers, _question_theme
from src.local_artifacts import (
    accepted_shadow_rules_path,
    founder_answer_applications_dir,
    founder_answer_packs_dir,
    latest_safety_triage_manifest_path,
    load_json,
    memory_proposals_path,
    safety_dispositions_path,
    shadow_suggestion_memory_path,
    unified_review_queue_path,
    write_json,
)
from src.memory_proposal_store import MemoryProposalStore, build_memory_proposal, load_storage_items
from src.safety_disposition_store import SafetyDispositionStore
from src.shadow_suggestion_memory import ShadowSuggestionMemory
from src.teachable_rule_memory import TeachableRuleMemory
from src.unresolved_gap_report import build_unresolved_gap_report_from_runtime


@dataclass(frozen=True)
class QueueReviewState:
    status: str = "pending"
    review_notes: str = ""
    approved_rule_ids: tuple[str, ...] = ()
    applied_decision_id: str = ""
    applied_application_path: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "review_notes": self.review_notes,
            "approved_rule_ids": list(self.approved_rule_ids),
            "applied_decision_id": self.applied_decision_id,
            "applied_application_path": self.applied_application_path,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "QueueReviewState":
        return cls(
            status=payload.get("status", "pending"),
            review_notes=payload.get("review_notes", ""),
            approved_rule_ids=tuple(payload.get("approved_rule_ids", [])),
            applied_decision_id=payload.get("applied_decision_id", ""),
            applied_application_path=payload.get("applied_application_path", ""),
            updated_at=payload.get("updated_at", ""),
        )


class UnifiedReviewQueue:
    def __init__(self, output_storage_dir: Path, provider_storage_dirs: list[tuple[str, Path]]) -> None:
        self._output_storage_dir = output_storage_dir
        self._provider_storage_dirs = provider_storage_dirs
        self._provider_dir_by_name = {provider: path for provider, path in provider_storage_dirs}
        self._path = unified_review_queue_path(output_storage_dir)

    @property
    def path(self) -> Path:
        return self._path

    def build_queue(
        self,
        *,
        runtime_report: dict | None = None,
        founder_answer_pack: dict | None = None,
    ) -> dict:
        runtime_report = runtime_report or self._latest_runtime_report()
        founder_answer_pack = founder_answer_pack or self._latest_founder_answer_pack()
        triage_manifest = self._latest_triage_manifest()
        preserved_states = self._load_review_states()
        items = []
        items.extend(self._memory_proposal_items())
        items.extend(self._shadow_suggestion_items())
        items.extend(self._safety_disposition_items())
        items.extend(self._runtime_llm_items(runtime_report, preserved_states))
        items.extend(self._founder_question_items(founder_answer_pack))
        items.extend(self._unresolved_gap_founder_question_items(runtime_report, triage_manifest, founder_answer_pack))
        ranked_items = self._rank_items(items, triage_manifest=triage_manifest)
        payload = {
            "generated_at": _now_iso(),
            "artifact_type": "unified-review-queue",
            "summary": self._summary(ranked_items),
            "sources": {
                "runtime_report_path": runtime_report.get("report_path", "") if runtime_report else "",
                "founder_answer_pack_path": founder_answer_pack.get("pack_path", "") if founder_answer_pack else "",
                "triage_manifest_path": str(latest_safety_triage_manifest_path(self._output_storage_dir))
                if latest_safety_triage_manifest_path(self._output_storage_dir).exists()
                else "",
                "shadow_suggestion_memory_path": str(shadow_suggestion_memory_path(self._output_storage_dir)),
                "memory_proposals_path": str(memory_proposals_path(self._output_storage_dir)),
                "accepted_shadow_rules_path": str(accepted_shadow_rules_path(self._output_storage_dir)),
            },
            "items": ranked_items,
        }
        write_json(self._path, payload)
        return payload

    def load_queue(self) -> dict:
        return load_json(self._path)

    def review_item(
        self,
        item_id: str,
        *,
        action: str,
        notes: str = "",
        labels: list[str] | None = None,
        answer_key: str | None = None,
        response_text: str | None = None,
    ) -> dict:
        if action not in {"approve", "reject", "answer"}:
            raise ValueError("Action must be approve, reject, or answer.")
        queue = self.load_queue()
        item = next((candidate for candidate in queue.get("items", []) if candidate.get("item_id") == item_id), None)
        if item is None:
            raise KeyError(f"Unknown review item: {item_id}")
        item_type = item.get("item_type", "")
        if action == "answer":
            if item_type != "founder-question":
                raise ValueError("Only founder-question items support answer actions.")
            result = self._answer_founder_question(item, answer_key=answer_key, response_text=response_text, notes=notes)
            refreshed = self.build_queue()
            return {**result, "queue_summary": refreshed.get("summary", {})}
        if item_type == "memory-proposal":
            result = self._review_memory_proposal(item, approved=action == "approve", notes=notes)
            refreshed = self.build_queue()
            return {**result, "queue_summary": refreshed.get("summary", {})}
        if item_type == "shadow-suggestion":
            result = self._review_shadow_suggestion(item, approved=action == "approve", notes=notes, labels=labels or [])
            refreshed = self.build_queue()
            return {**result, "queue_summary": refreshed.get("summary", {})}
        if item_type == "safety-disposition":
            result = self._review_safety_disposition(item, approved=action == "approve", notes=notes)
            refreshed = self.build_queue()
            return {**result, "queue_summary": refreshed.get("summary", {})}
        if item_type == "runtime-llm-candidate":
            result = self._review_runtime_llm_candidate(item, approved=action == "approve", notes=notes, labels=labels or [])
            refreshed = self.build_queue()
            return {**result, "queue_summary": refreshed.get("summary", {})}
        raise ValueError(f"Unsupported review item type: {item_type}")

    def _review_memory_proposal(self, item: dict, *, approved: bool, notes: str) -> dict:
        store = MemoryProposalStore(memory_proposals_path(self._output_storage_dir))
        rules_memory = TeachableRuleMemory(accepted_shadow_rules_path(self._output_storage_dir))
        updated = store.review_proposal(
            item["source_ref"]["proposal_id"],
            "approved" if approved else "rejected",
            rules_memory=rules_memory if approved else None,
            review_notes=notes,
        )
        return {
            "item_id": item["item_id"],
            "item_type": item["item_type"],
            "status": updated.status,
            "approved_rule_ids": [updated.approved_rule_id] if updated.approved_rule_id else [],
        }

    def _review_shadow_suggestion(
        self,
        item: dict,
        *,
        approved: bool,
        notes: str,
        labels: list[str],
    ) -> dict:
        memory = ShadowSuggestionMemory(shadow_suggestion_memory_path(self._output_storage_dir))
        payload = item.get("decision_payload", {})
        updated = memory.review_candidate(
            payload.get("provider", ""),
            payload.get("sender_key", ""),
            payload.get("subject_key", ""),
            "accepted" if approved else "rejected",
            accepted_labels=labels,
            review_notes=notes,
        )
        exported_rule_ids: list[str] = []
        if approved:
            exported = memory.export_accepted_rules(accepted_shadow_rules_path(self._output_storage_dir))
            exported_rule_ids = [
                rule.id
                for rule in exported
                if rule.providers == (updated.provider,) and rule.provenance.get("sender_key") == updated.sender_key
            ]
        return {
            "item_id": item["item_id"],
            "item_type": item["item_type"],
            "status": "approved" if approved else "rejected",
            "approved_rule_ids": exported_rule_ids,
        }

    def _review_safety_disposition(self, item: dict, *, approved: bool, notes: str) -> dict:
        provider = item.get("provider", "")
        storage_dir = self._provider_dir_by_name.get(provider)
        if storage_dir is None:
            raise KeyError(f"Unknown provider storage for safety disposition: {provider}")
        store = SafetyDispositionStore(safety_dispositions_path(storage_dir))
        updated = store.review_disposition(
            item["source_ref"]["disposition_id"],
            "approved" if approved else "rejected",
            review_notes=notes,
        )
        return {
            "item_id": item["item_id"],
            "item_type": item["item_type"],
            "status": updated.status,
            "approved_rule_ids": [],
        }

    def _review_runtime_llm_candidate(
        self,
        item: dict,
        *,
        approved: bool,
        notes: str,
        labels: list[str],
    ) -> dict:
        review_state = self._load_review_states()
        payload = item.get("decision_payload", {})
        now = _now_iso()
        status = "rejected"
        approved_rule_ids: list[str] = []
        if approved:
            provider = item.get("provider", "")
            provider_dir = self._provider_dir_by_name.get(provider)
            if provider_dir is None:
                raise KeyError(f"Unknown provider storage for runtime candidate: {provider}")
            rules_memory = TeachableRuleMemory(accepted_shadow_rules_path(self._output_storage_dir))
            proposal_store = MemoryProposalStore(memory_proposals_path(self._output_storage_dir))
            storage_items = load_storage_items(provider_dir, provider)
            approved_labels = labels or list(payload.get("suggested_labels", []))
            if not approved_labels:
                raise ValueError("Runtime LLM approvals need at least one label.")
            for label in approved_labels:
                proposal = build_memory_proposal(
                    provider=provider,
                    account_id=item.get("account_id", ""),
                    source_batch_id=payload.get("source_batch_id", ""),
                    selected_items=list(payload.get("source_examples", [])),
                    scope="sender-cluster",
                    label=label,
                    explanation=(
                        f"Promoted from runtime LLM candidate {item['item_id']} with confidence "
                        f"{payload.get('confidence', 'low')}."
                    ),
                    storage_items=storage_items,
                )
                proposal_store.save_proposal(proposal)
                updated = proposal_store.review_proposal(
                    proposal.id,
                    "approved",
                    rules_memory=rules_memory,
                    review_notes=notes,
                )
                if updated.approved_rule_id:
                    approved_rule_ids.append(updated.approved_rule_id)
            status = "approved"
        review_state[item["item_id"]] = QueueReviewState(
            status=status,
            review_notes=notes,
            approved_rule_ids=tuple(approved_rule_ids),
            updated_at=now,
        )
        self._write_review_states(review_state)
        return {
            "item_id": item["item_id"],
            "item_type": item["item_type"],
            "status": status,
            "approved_rule_ids": approved_rule_ids,
        }

    def _answer_founder_question(
        self,
        item: dict,
        *,
        answer_key: str | None,
        response_text: str | None,
        notes: str,
    ) -> dict:
        payload = item.get("decision_payload", {})
        question = dict(payload.get("question", {}))
        if not question:
            raise ValueError("Founder question item is missing question payload.")
        answer_options = list(question.get("answer_options", []))
        if answer_key:
            option = next((candidate for candidate in answer_options if candidate.get("answer_key") == answer_key), None)
            if option is None:
                raise KeyError(f"Unknown founder answer key: {answer_key}")
            chosen_text = response_text or option.get("description", answer_key)
        elif response_text:
            chosen_text = response_text
        else:
            raise ValueError("Founder question answers require answer_key or response_text.")
        pack = {
            "questions": [question],
            "summary": {"question_count": 1, "answer_option_count": len(answer_options)},
        }
        decision = save_founder_answer_decision(
            self._output_storage_dir,
            founder_answer_pack=pack,
            question_id=question.get("question_id", ""),
            response_text=chosen_text,
        )
        review_pack = self._review_pack_for_question(item)
        application = apply_founder_answer_decision(
            self._output_storage_dir,
            decision=decision,
            provider_storage_dirs=self._provider_storage_dirs,
            review_notes=notes,
            review_pack=review_pack,
        )
        review_state = self._load_review_states()
        review_state[item["item_id"]] = QueueReviewState(
            status="applied",
            review_notes=notes,
            approved_rule_ids=tuple(application.get("approved_rule_ids", [])),
            applied_decision_id=decision.get("decision_id", ""),
            applied_application_path=application.get("application_path", ""),
            updated_at=_now_iso(),
        )
        self._write_review_states(review_state)
        return {
            "item_id": item["item_id"],
            "item_type": item["item_type"],
            "status": "applied",
            "approved_rule_ids": list(application.get("approved_rule_ids", [])),
            "application_path": application.get("application_path", ""),
        }

    def _memory_proposal_items(self) -> list[dict]:
        store = MemoryProposalStore(memory_proposals_path(self._output_storage_dir))
        items = []
        for proposal in store.list_proposals():
            items.append(
                {
                    "item_id": f"memory-proposal:{proposal.id}",
                    "item_type": "memory-proposal",
                    "provider": proposal.provider,
                    "account_id": proposal.account_id,
                    "status": proposal.status,
                    "priority_score": proposal.preview.get("match_count", 0),
                    "title": f"Memory proposal: {proposal.label} via {proposal.scope}",
                    "source_ref": {
                        "proposal_id": proposal.id,
                        "artifact_path": str(memory_proposals_path(self._output_storage_dir)),
                    },
                    "summary": {
                        "label": proposal.label,
                        "scope": proposal.scope,
                        "match_count": proposal.preview.get("match_count", 0),
                        "source_message_count": len(proposal.source_message_ids),
                    },
                    "decision_payload": proposal.to_dict(),
                    "review_notes": proposal.review_notes,
                    "created_at": proposal.created_at,
                    "updated_at": proposal.updated_at,
                }
            )
        return items

    def _shadow_suggestion_items(self) -> list[dict]:
        memory = ShadowSuggestionMemory(shadow_suggestion_memory_path(self._output_storage_dir))
        items = []
        for candidate in memory.list_candidates():
            items.append(
                {
                    "item_id": f"shadow-suggestion:{candidate.provider}:{candidate.sender_key}:{candidate.subject_key}",
                    "item_type": "shadow-suggestion",
                    "provider": candidate.provider,
                    "account_id": "",
                    "status": self._normalized_shadow_status(candidate.status),
                    "priority_score": candidate.count,
                    "title": f"Shadow suggestion: {candidate.provider} {candidate.sender_key}",
                    "source_ref": {
                        "provider": candidate.provider,
                        "sender_key": candidate.sender_key,
                        "subject_key": candidate.subject_key,
                        "artifact_path": str(shadow_suggestion_memory_path(self._output_storage_dir)),
                    },
                    "summary": {
                        "suggested_labels": list(candidate.suggested_labels),
                        "accepted_labels": list(candidate.accepted_labels),
                        "family_count": candidate.count,
                        "confidence": candidate.confidence,
                    },
                    "decision_payload": candidate.to_dict(),
                    "review_notes": candidate.review_notes,
                    "created_at": candidate.created_at,
                    "updated_at": candidate.updated_at,
                }
            )
        return items

    def _safety_disposition_items(self) -> list[dict]:
        items = []
        for provider, storage_dir in self._provider_storage_dirs:
            store = SafetyDispositionStore(safety_dispositions_path(storage_dir))
            for disposition in store.list_dispositions():
                items.append(
                    {
                        "item_id": f"safety-disposition:{provider}:{disposition.id}",
                        "item_type": "safety-disposition",
                        "provider": provider,
                        "account_id": disposition.account_id,
                        "status": disposition.status,
                        "priority_score": disposition.preview.get("match_count", 0) + 25,
                        "title": f"Safety disposition: {disposition.disposition}",
                        "source_ref": {
                            "disposition_id": disposition.id,
                            "artifact_path": str(safety_dispositions_path(storage_dir)),
                        },
                        "summary": {
                            "scope": disposition.scope,
                            "disposition": disposition.disposition,
                            "match_count": disposition.preview.get("match_count", 0),
                        },
                        "decision_payload": disposition.to_dict(),
                        "review_notes": disposition.review_notes,
                        "created_at": disposition.created_at,
                        "updated_at": disposition.updated_at,
                    }
                )
        return items

    def _runtime_llm_items(self, runtime_report: dict | None, preserved_states: dict[str, QueueReviewState]) -> list[dict]:
        if not runtime_report:
            return []
        grouped: dict[tuple, dict] = {}
        for provider_report in runtime_report.get("providers", {}).values():
            for outcome in provider_report.get("outcomes", []):
                if outcome.get("stage") != "llm-escalation":
                    continue
                labels = tuple(outcome.get("labels", []))
                subject_key = outcome.get("subject_key") or _normalized_subject(outcome.get("subject", ""))
                queue_key = (
                    outcome.get("provider", ""),
                    outcome.get("sender_key", ""),
                    subject_key,
                    labels,
                    outcome.get("decision", {}).get("safety_lane", "ordinary"),
                )
                group = grouped.setdefault(
                    queue_key,
                    {
                        "provider": outcome.get("provider", ""),
                        "account_id": outcome.get("account_id", ""),
                        "sender_key": outcome.get("sender_key", ""),
                        "subject_key": subject_key,
                        "suggested_labels": list(labels),
                        "confidence": outcome.get("decision", {}).get("confidence", "low"),
                        "rationale": outcome.get("llm_rationale", ""),
                        "safety_lane": outcome.get("decision", {}).get("safety_lane", "ordinary"),
                        "source_batch_id": outcome.get("batch_id", ""),
                        "source_examples": [],
                        "count": 0,
                        "llm_model": outcome.get("decision_provenance", {}).get("llm_model", ""),
                    },
                )
                group["count"] += 1
                group["source_examples"].append(
                    {
                        "provider": outcome.get("provider", ""),
                        "account_id": outcome.get("account_id", ""),
                        "batch_id": outcome.get("batch_id", ""),
                        "message_id": outcome.get("message_id", ""),
                        "sender": outcome.get("sender", ""),
                        "subject": outcome.get("subject", ""),
                        "date": "",
                        "final_labels": list(outcome.get("labels", [])),
                    }
                )
                if not group["rationale"]:
                    group["rationale"] = outcome.get("llm_rationale", "")
        items = []
        for key, group in grouped.items():
            item_id = _runtime_candidate_id(*key)
            review_state = preserved_states.get(item_id, QueueReviewState())
            items.append(
                {
                    "item_id": item_id,
                    "item_type": "runtime-llm-candidate",
                    "provider": group["provider"],
                    "account_id": group["account_id"],
                    "status": review_state.status,
                    "priority_score": group["count"] + (15 if group["safety_lane"] != "ordinary" else 0),
                    "title": f"Runtime LLM candidate: {group['provider']} {group['sender_key']}",
                    "source_ref": {
                        "report_path": runtime_report.get("report_path", ""),
                        "provider": group["provider"],
                        "sender_key": group["sender_key"],
                        "subject_key": group["subject_key"],
                    },
                    "summary": {
                        "suggested_labels": list(group["suggested_labels"]),
                        "family_count": group["count"],
                        "confidence": group["confidence"],
                        "safety_lane": group["safety_lane"],
                    },
                    "decision_payload": {
                        **group,
                        "item_id": item_id,
                    },
                    "review_notes": review_state.review_notes,
                    "created_at": review_state.updated_at or runtime_report.get("generated_at", _now_iso()),
                    "updated_at": review_state.updated_at or runtime_report.get("generated_at", _now_iso()),
                    "approved_rule_ids": list(review_state.approved_rule_ids),
                }
            )
        return items

    def _founder_question_items(self, founder_answer_pack: dict | None) -> list[dict]:
        if not founder_answer_pack:
            return []
        applied_by_question_id = self._applied_question_index()
        items = []
        for question in founder_answer_pack.get("questions", []):
            application = applied_by_question_id.get(question.get("question_id", ""))
            status = "applied" if application else "pending"
            items.append(
                {
                    "item_id": f"founder-question:{question.get('question_id', '')}",
                    "item_type": "founder-question",
                    "provider": ",".join(question.get("providers", [])),
                    "account_id": "",
                    "status": status,
                    "priority_score": int(question.get("estimated_unblocked_messages", 0)),
                    "title": question.get("title", "Founder question"),
                    "source_ref": {
                        "question_id": question.get("question_id", ""),
                        "artifact_path": founder_answer_pack.get("pack_path", ""),
                    },
                    "summary": {
                        "theme": question.get("theme", ""),
                        "family_count": question.get("family_count", 0),
                        "estimated_unblocked_messages": question.get("estimated_unblocked_messages", 0),
                        "answer_option_count": len(question.get("answer_options", [])),
                    },
                    "decision_payload": {"question": question},
                    "review_notes": application.get("review_notes", "") if application else "",
                    "created_at": founder_answer_pack.get("generated_at", _now_iso()),
                    "updated_at": application.get("generated_at", founder_answer_pack.get("generated_at", _now_iso()))
                    if application
                    else founder_answer_pack.get("generated_at", _now_iso()),
                    "approved_rule_ids": list(application.get("approved_rule_ids", [])) if application else [],
                }
            )
        return items

    def _unresolved_gap_founder_question_items(
        self,
        runtime_report: dict | None,
        triage_manifest: dict | None,
        founder_answer_pack: dict | None,
    ) -> list[dict]:
        if not runtime_report:
            return []
        existing_question_ids = {
            question.get("question_id", "")
            for question in (founder_answer_pack or {}).get("questions", [])
            if question.get("question_id")
        }
        gap_report = build_unresolved_gap_report_from_runtime(runtime_report, manifest=triage_manifest)
        by_provider_sender: dict[tuple[str, str], list[dict]] = {}
        for provider, payload in runtime_report.get("providers", {}).items():
            for outcome in payload.get("outcomes", []):
                if outcome.get("stage") != "unresolved":
                    continue
                key = (provider, outcome.get("sender_key", ""))
                by_provider_sender.setdefault(key, []).append(outcome)
        storage_items_by_provider = {
            provider: load_storage_items(path, provider)
            for provider, path in self._provider_storage_dirs
        }
        applied_by_question_id = self._applied_question_index()
        items = []
        for action in gap_report.get("recommended_actions", []):
            if action.get("action_type") not in {"hotspot-review", "family-review", "safety-review"}:
                continue
            provider = action.get("provider_scope", "")
            sender_key = action.get("sender_key", "")
            examples = by_provider_sender.get((provider, sender_key), [])
            if not examples:
                continue
            question = _build_hotspot_founder_question(
                action=action,
                examples=examples,
                storage_items=storage_items_by_provider.get(provider, []),
            )
            question_id = question.get("question_id", "")
            if not question_id or question_id in existing_question_ids:
                continue
            application = applied_by_question_id.get(question_id)
            items.append(
                {
                    "item_id": f"founder-question:{question_id}",
                    "item_type": "founder-question",
                    "provider": provider,
                    "account_id": examples[0].get("account_id", ""),
                    "status": "applied" if application else "pending",
                    "priority_score": int(question.get("estimated_unblocked_messages", 0)),
                    "title": question.get("title", "Founder question"),
                    "source_ref": {
                        "question_id": question_id,
                        "source": "unresolved-gap",
                        "runtime_report_path": runtime_report.get("report_path", ""),
                    },
                    "summary": {
                        "theme": question.get("theme", ""),
                        "family_count": question.get("family_count", 0),
                        "estimated_unblocked_messages": question.get("estimated_unblocked_messages", 0),
                        "answer_option_count": len(question.get("answer_options", [])),
                        "example_subject": question.get("example_subject", ""),
                        "example_sender": sender_key,
                    },
                    "decision_payload": {"question": question},
                    "review_notes": application.get("review_notes", "") if application else "",
                    "created_at": runtime_report.get("generated_at", _now_iso()),
                    "updated_at": application.get("generated_at", runtime_report.get("generated_at", _now_iso()))
                    if application
                    else runtime_report.get("generated_at", _now_iso()),
                    "approved_rule_ids": list(application.get("approved_rule_ids", [])) if application else [],
                }
            )
        return items

    def _summary(self, items: list[dict]) -> dict:
        status_counts = Counter(item.get("status", "pending") for item in items)
        type_counts = Counter(item.get("item_type", "") for item in items)
        pending_by_type = Counter(item.get("item_type", "") for item in items if item.get("status") == "pending")
        pending_items = [item for item in items if item.get("status") == "pending"]
        provider_counts = Counter(item.get("provider", "") for item in pending_items if item.get("provider"))
        return {
            "item_count": len(items),
            "status_counts": dict(status_counts),
            "type_counts": dict(type_counts),
            "pending_by_type": dict(pending_by_type),
            "pending_count": len(pending_items),
            "provider_counts": dict(provider_counts),
            "top_pending_items": [
                {
                    "item_id": item.get("item_id", ""),
                    "item_type": item.get("item_type", ""),
                    "title": item.get("title", ""),
                    "provider": item.get("provider", ""),
                    "rank_score": item.get("rank", {}).get("score", 0),
                }
                for item in pending_items[:5]
            ],
        }

    def _load_review_states(self) -> dict[str, QueueReviewState]:
        if not self._path.exists():
            return {}
        payload = load_json(self._path)
        states = {}
        for item in payload.get("items", []):
            if item.get("item_type") != "runtime-llm-candidate":
                continue
            states[item["item_id"]] = QueueReviewState(
                status=item.get("status", "pending"),
                review_notes=item.get("review_notes", ""),
                approved_rule_ids=tuple(item.get("approved_rule_ids", [])),
                updated_at=item.get("updated_at", ""),
            )
        return states

    def _write_review_states(self, states: dict[str, QueueReviewState]) -> None:
        payload = self.load_queue() if self._path.exists() else {"items": []}
        rewritten = []
        for item in payload.get("items", []):
            state = states.get(item.get("item_id", ""))
            if item.get("item_type") == "runtime-llm-candidate" and state is not None:
                updated = dict(item)
                updated["status"] = state.status
                updated["review_notes"] = state.review_notes
                updated["updated_at"] = state.updated_at or item.get("updated_at", "")
                updated["approved_rule_ids"] = list(state.approved_rule_ids)
                rewritten.append(updated)
                continue
            if item.get("item_type") == "founder-question" and state is not None:
                updated = dict(item)
                updated["status"] = state.status
                updated["review_notes"] = state.review_notes
                updated["updated_at"] = state.updated_at or item.get("updated_at", "")
                updated["approved_rule_ids"] = list(state.approved_rule_ids)
                rewritten.append(updated)
                continue
            rewritten.append(item)
        payload["generated_at"] = _now_iso()
        payload["items"] = rewritten
        payload["summary"] = self._summary(rewritten)
        write_json(self._path, payload)

    def _applied_question_index(self) -> dict[str, dict]:
        applications = {}
        applications_dir = founder_answer_applications_dir(self._output_storage_dir)
        if not applications_dir.exists():
            return applications
        for path in sorted(applications_dir.glob("*.json")):
            payload = load_json(path)
            question_id = payload.get("question_id", "")
            if question_id:
                applications[question_id] = payload
        return applications

    def _latest_runtime_report(self) -> dict | None:
        runtime_dir = self._output_storage_dir / "runtime_cascades"
        if not runtime_dir.exists():
            return None
        matches = sorted(runtime_dir.glob("*.json"))
        if not matches:
            return None
        report = load_json(matches[-1])
        report["report_path"] = str(matches[-1])
        return report

    def _latest_founder_answer_pack(self) -> dict | None:
        packs_dir = founder_answer_packs_dir(self._output_storage_dir)
        if not packs_dir.exists():
            return None
        matches = sorted(packs_dir.glob("*.json"))
        if not matches:
            return None
        pack = load_json(matches[-1])
        pack["pack_path"] = str(matches[-1])
        return pack

    def _latest_triage_manifest(self) -> dict | None:
        path = latest_safety_triage_manifest_path(self._output_storage_dir)
        if not path.exists():
            return None
        manifest = load_json(path)
        manifest["manifest_path"] = str(path)
        return manifest

    def _review_pack_for_question(self, item: dict) -> dict:
        source = item.get("source_ref", {})
        artifact_path = source.get("artifact_path", "")
        if artifact_path:
            return {"pack_path": artifact_path}
        manifest = self._latest_triage_manifest()
        review_pack_path = (manifest or {}).get("artifacts", {}).get("review_pack_path", "")
        if review_pack_path:
            path = Path(review_pack_path)
            if path.exists():
                return load_json(path)
        return {}

    def _normalized_shadow_status(self, status: str) -> str:
        if status == "accepted":
            return "approved"
        return status

    def _rank_items(self, items: list[dict], *, triage_manifest: dict | None) -> list[dict]:
        provider_driver_score = {
            item.get("provider", ""): int(item.get("driver_score", 0))
            for item in (triage_manifest or {}).get("provider_drivers", [])
        }
        review_payoff = {
            (item.get("provider", ""), item.get("sender_key", ""), item.get("subject_key", "")): int(
                item.get("expected_resolved_messages", 0)
            )
            for item in (triage_manifest or {}).get("next_review_payoffs", [])
        }
        ranked = []
        for item in items:
            updated = dict(item)
            rank = _rank_item(updated, provider_driver_score=provider_driver_score, review_payoff=review_payoff)
            updated["rank"] = rank
            ranked.append(updated)
        ranked.sort(
            key=lambda item: (
                item.get("status") != "pending",
                -item.get("rank", {}).get("score", 0),
                item.get("item_type", ""),
                item.get("provider", ""),
                item.get("title", ""),
            )
        )
        return ranked


def _runtime_candidate_id(
    provider: str,
    sender_key: str,
    subject_key: str,
    labels: tuple[str, ...],
    safety_lane: str,
) -> str:
    rendered_labels = ",".join(labels) or "unlabeled"
    return f"runtime-llm:{provider}:{sender_key}:{subject_key}:{rendered_labels}:{safety_lane}"


def _normalized_subject(subject: str) -> str:
    return "".join("#" if char.isdigit() else char for char in (subject or "").strip().lower())


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rank_item(
    item: dict,
    *,
    provider_driver_score: dict[str, int],
    review_payoff: dict[tuple[str, str, str], int],
) -> dict:
    provider = item.get("provider", "")
    item_type = item.get("item_type", "")
    summary = item.get("summary", {})
    source_ref = item.get("source_ref", {})
    score = 0
    reasons: list[str] = []
    lane = "review"
    if item.get("status") != "pending":
        return {"score": -1, "lane": "done", "reasons": ["Already reviewed or applied."]}

    score += int(item.get("priority_score", 0))
    driver_bonus = provider_driver_score.get(provider, 0)
    if driver_bonus:
        score += driver_bonus
        reasons.append(f"{provider} is currently a strong backlog driver.")

    if item_type == "founder-question":
        lane = "preference"
        gain = int(summary.get("estimated_unblocked_messages", 0))
        score += 60 + gain
        if gain:
            reasons.append(f"One answer may unblock about {gain} messages.")
    elif item_type == "safety-disposition":
        lane = "safety"
        match_count = int(summary.get("match_count", 0))
        score += 70 + (match_count * 2)
        reasons.append("Safety lane items should be resolved before ordinary taxonomy cleanup.")
    elif item_type == "runtime-llm-candidate":
        lane = "llm"
        family_count = int(summary.get("family_count", 0))
        payoff = review_payoff.get(
            (provider, source_ref.get("sender_key", ""), source_ref.get("subject_key", "")),
            family_count,
        )
        score += 45 + family_count + payoff
        if summary.get("safety_lane") and summary.get("safety_lane") != "ordinary":
            score += 20
            reasons.append("This model suggestion is attached to a caution lane.")
        reasons.append(f"Approving this could teach a recurring family of about {family_count} messages.")
    elif item_type == "memory-proposal":
        lane = "memory"
        match_count = int(summary.get("match_count", 0))
        score += 35 + (match_count * 2)
        reasons.append(f"This memory proposal affects about {match_count} messages.")
    elif item_type == "shadow-suggestion":
        lane = "shadow"
        family_count = int(summary.get("family_count", 0))
        payoff = review_payoff.get(
            (provider, source_ref.get("sender_key", ""), source_ref.get("subject_key", "")),
            family_count,
        )
        score += 25 + family_count + payoff
        reasons.append(f"This shadow family appears about {family_count} times.")

    confidence = summary.get("confidence", "")
    if confidence == "high":
        score += 6
        reasons.append("The current suggestion confidence is high.")
    elif confidence == "medium":
        score += 3

    if not reasons:
        reasons.append("Pending review.")
    return {"score": score, "lane": lane, "reasons": reasons[:3]}


def _build_hotspot_founder_question(*, action: dict, examples: list[dict], storage_items: list[dict]) -> dict:
    provider = action.get("provider_scope", "")
    sender_key = action.get("sender_key", "")
    subject_key = action.get("subject_key", "")
    target = {
        "provider": provider,
        "sender_key": sender_key,
        "subject_key": subject_key,
        "suggested_labels": [],
        "question_lane": "preference-question",
        "examples": [
            {
                "provider": provider,
                "account_id": example.get("account_id", ""),
                "batch_id": example.get("batch_id", ""),
                "message_id": example.get("message_id", ""),
                "sender": example.get("sender", ""),
                "subject": example.get("subject", ""),
            }
            for example in examples[:3]
        ],
    }
    theme = _question_theme(target)
    config = QUESTION_THEME_CONFIG.get(theme, QUESTION_THEME_CONFIG["taxonomy-gap"])
    answer_options = []
    for answer in _draft_answers(theme, []):
        answer_key = answer.get("answer_key", "")
        label, scope = ANSWER_LABELS.get((theme, answer_key), (None, None))
        scope = _hotspot_scope_for_answer(theme, answer_key, scope)
        proposal_drafts = []
        if label and scope:
            proposal = build_memory_proposal(
                provider=provider,
                account_id=examples[0].get("account_id", ""),
                source_batch_id=examples[0].get("batch_id", ""),
                selected_items=examples[:3],
                scope=scope,
                label=label,
                explanation=(
                    f"Drafted from unresolved hotspot founder question for recurring family "
                    f"{sender_key} / {subject_key or examples[0].get('subject', '')}."
                ),
                storage_items=storage_items,
            )
            proposal_payload = proposal.to_dict()
            proposal_payload["count"] = int(action.get("expected_gain", 0))
            proposal_drafts.append(proposal_payload)
        answer_options.append(
            {
                "answer_key": answer.get("answer_key", ""),
                "description": answer.get("description", ""),
                "proposal_drafts": proposal_drafts,
                "projection": {
                    "proposal_count": len(proposal_drafts),
                    "estimated_resolved_messages": int(action.get("expected_gain", 0)) if proposal_drafts else 0,
                },
            }
        )
    family_count = int(action.get("observed_unresolved_count", action.get("expected_gain", 0)))
    example_subject = examples[0].get("subject", "")
    return {
        "question_id": _hotspot_question_id(provider, sender_key),
        "theme": theme,
        "title": f"How should recurring mail from {sender_key} be handled?",
        "prompt": (
            f"This unresolved family appeared about {family_count} times in the latest run. "
            f"Example subject: {example_subject or '(missing subject)'}"
        ),
        "providers": [provider] if provider else [],
        "family_count": 1,
        "estimated_unblocked_messages": family_count,
        "answer_options": answer_options,
        "example_subject": example_subject,
    }


def _hotspot_question_id(provider: str, sender_key: str) -> str:
    provider_fragment = provider or "unknown-provider"
    sender_fragment = "".join(char if char.isalnum() else "-" for char in (sender_key or "unknown-sender").lower()).strip(
        "-"
    )
    return f"question-hotspot-{provider_fragment}-{sender_fragment or 'unknown-sender'}"


def _hotspot_scope_for_answer(theme: str, answer_key: str, default_scope: str | None) -> str | None:
    if default_scope is None:
        return None
    if theme == "marketing-preference":
        return "sender"
    if theme == "direct-message-handling" and answer_key == "personal_default":
        return "sender"
    return default_scope
