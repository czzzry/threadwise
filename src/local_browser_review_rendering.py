import json
from collections import Counter
from html import escape
from pathlib import Path

from src.label_taxonomy import CANONICAL_LABEL_ORDER, allowed_gmail_labels, gmail_label_name
from src.local_artifacts import safety_dispositions_path
from src.local_batch_summary import load_batch, summarize_batch
from src.safety_disposition_store import SafetyDispositionStore, approved_safety_context, matches_safety_context
from src.sender_utils import normalized_sender_email
from src.trusted_sender_store import TrustedSenderStore


class LocalBrowserReviewRenderingMixin:
    def render_page(self, selected_batch_id: str | None = None, selected_evaluation_id: str | None = None) -> str:
        if selected_evaluation_id:
            heading = f"Shadow evaluation {selected_evaluation_id}"
            subheading = (
                "Compare the current reviewed labels against OpenAI shadow suggestions. "
                "Only disagreements are shown here."
            )
            batch_id = ""
            try:
                body_html = self._render_shadow_evaluation(selected_evaluation_id)
            except Exception as exc:
                message = str(exc)
                if isinstance(exc, FileNotFoundError):
                    message = f"Unknown evaluation id: {selected_evaluation_id}"
                body_html = (
                    '<section class="panel error-panel"><h2>Could not load shadow evaluation.</h2>'
                    f'<p class="meta">{escape(message)}</p></section>'
                )
            return self._render_document(heading, subheading, batch_id, body_html)

        active_batch_id = selected_batch_id if selected_batch_id is not None else self._batch_id
        if active_batch_id is None:
            body_html = self._render_workbench()
            heading = "Stored batch workbench"
            subheading = (
                "Local-only review workbench. Open stored batches here. "
                "No Gmail fetches or writes happen in this surface."
            )
            batch_id = ""
        else:
            heading = f"Review stored batch {active_batch_id}"
            subheading = (
                "Local-only review surface. Decisions are saved to the stored batch. "
                "No Gmail fetches or writes happen here."
            )
            batch_id = active_batch_id
            try:
                batch = self._load_batch(active_batch_id)
                items = batch["items"]
                pending_items = [item for item in items if item.get("review_state") != "reviewed"]
                body_html = self._render_summary(build_summary(items))
                if pending_items:
                    body_html += self._render_pending_items(active_batch_id, pending_items)
                else:
                    body_html += (
                        '<section class="panel"><h2>No pending items remain for this batch.</h2>'
                        '<p class="meta">All review decisions are already saved locally. '
                        'Reviewed items remain frozen by the existing review contract.</p></section>'
                    )
            except Exception as exc:
                message = str(exc)
                if isinstance(exc, FileNotFoundError):
                    message = f"Unknown batch id: {active_batch_id}"
                body_html = (
                    '<section class="panel error-panel"><h2>Could not load stored batch.</h2>'
                    f'<p class="meta">{escape(message)}</p></section>'
                )
        return self._render_document(heading, subheading, batch_id, body_html)

    def _render_document(self, heading: str, subheading: str, batch_id: str, body_html: str) -> str:
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stored Batch Review</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3efe4;
      --panel: #fffdf8;
      --ink: #1f1a14;
      --muted: #6b6255;
      --line: #d7cfbf;
      --accent: #0f766e;
      --accent-soft: #d8f3ef;
      --error: #9f1239;
    }
    body { margin: 0; font-family: Georgia, "Times New Roman", serif; background: linear-gradient(180deg, #f7f1e7 0%, var(--bg) 100%); color: var(--ink); }
    main { max-width: 1100px; margin: 0 auto; padding: 32px 20px 60px; }
    h1 { margin-bottom: 8px; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 18px; box-shadow: 0 10px 30px rgba(31, 26, 20, 0.06); margin-bottom: 20px; }
    .error-panel { border-color: #f0b7c5; background: #fff5f7; color: var(--error); }
    .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
    .metric { background: #f8f5ed; border-radius: 12px; padding: 12px; }
    .items { display: grid; gap: 16px; }
    .item { border: 1px solid var(--line); border-radius: 14px; padding: 16px; background: #fffdfa; }
    .taxonomy { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .taxonomy-option { border: 1px solid var(--line); background: white; border-radius: 999px; padding: 8px 12px; cursor: pointer; }
    .taxonomy-option.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
    .actionability { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .actionability-option { border: 1px solid var(--line); background: white; border-radius: 999px; padding: 8px 12px; cursor: pointer; }
    .actionability-option.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
    .actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
    .action { border: 0; border-radius: 999px; padding: 10px 14px; cursor: pointer; background: var(--ink); color: white; }
    .secondary { background: #ebe4d7; color: var(--ink); }
    .danger { background: #7f1d1d; color: white; }
    .meta { color: var(--muted); font-size: 0.95rem; }
    .pill { display: inline-block; padding: 4px 8px; border-radius: 999px; background: #f0eadf; margin-right: 6px; margin-top: 6px; }
    .field { margin: 6px 0; }
    .field strong { display: inline-block; min-width: 92px; }
    details.context-panel { margin-top: 12px; padding: 12px; border: 1px dashed var(--line); border-radius: 12px; background: #fcf8f0; }
    details.context-panel summary { cursor: pointer; font-weight: 600; }
    .context-copy { margin-top: 10px; white-space: pre-wrap; overflow-wrap: anywhere; }
    .compare-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 12px; }
    .compare-card { border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: #f8f5ed; }
    .compare-card h3 { margin-top: 0; margin-bottom: 10px; font-size: 1rem; }
    .unsubscribe-row { display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: start; }
    .checkbox { margin-top: 6px; width: 18px; height: 18px; }
    #fetch-status { position: sticky; top: 0; z-index: 5; }
    .status-banner { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; border-radius: 12px; padding: 12px 14px; margin: 12px 0 20px; }
    .teaching-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(240px, 0.8fr); gap: 12px; align-items: start; }
    .teaching-input { width: 100%; min-height: 92px; border: 1px solid var(--line); border-radius: 12px; padding: 10px; font: inherit; background: #fffdfa; }
    .teaching-preview { border: 1px dashed var(--line); border-radius: 12px; padding: 12px; background: #fcf8f0; min-height: 80px; }
    .teaching-select, .teaching-label-select { width: 100%; border: 1px solid var(--line); border-radius: 12px; padding: 10px; font: inherit; background: #fffdfa; }
    .teaching-subgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
    .teach-select { display: inline-flex; align-items: center; gap: 8px; margin: 8px 0; }
    .rule-match { background: var(--accent-soft); color: var(--accent); border: 1px solid #9dd8ca; }
    .rule-inline-actions { display: inline-flex; gap: 6px; margin-left: 8px; }
    .tiny-action { border: 0; border-radius: 999px; padding: 4px 8px; cursor: pointer; background: #ebe4d7; color: var(--ink); font-size: 0.78rem; }
    .safety-priority { background: #fff4e5; border: 1px solid #f59e0b; color: #92400e; }
    .safety-priority-card { border-color: #f59e0b; box-shadow: 0 10px 30px rgba(245, 158, 11, 0.12); }
    @media (max-width: 760px) { .teaching-grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <h1>__HEADING__</h1>
    <p class="meta">__SUBHEADING__</p>
    <div id="fetch-status" class="meta"></div>
    __BODY_HTML__
  </main>
  <script>
    const labelMap = {
      "EA/Travel": "travel",
      "EA/Receipts": "receipt-billing",
      "EA/Orders": "shopping-order",
      "EA/Finance": "financial-account",
      "EA/Newsletter": "newsletter",
      "EA/Promotions": "promotions",
      "EA/Account": "account-security",
      "EA/Calendar": "calendar-event",
      "EA/Personal": "personal",
      "EA/Work": "job-related",
      "EA/LowValue": "spam-low-value",
      "EA/NeedsAction": "reply-needed"
    };
    function selectedLabels(card) {
      return [...card.querySelectorAll(".taxonomy-option.active")].map((button) => labelMap[button.dataset.label]);
    }
    function selectedActionability(card) {
      const active = card.querySelector(".actionability-option.active");
      return active ? active.dataset.actionability : null;
    }
    async function saveDecision(card, decision) {
      const payload = {
        message_id: card.dataset.messageId,
        decision,
        final_labels: decision === "edit" ? selectedLabels(card) : [],
        actionability: selectedActionability(card)
      };
      const response = await fetch("/api/batches/__BATCH_ID__/decisions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const errorPayload = await response.json();
        window.alert(errorPayload.error || "Failed to save review decision.");
        return;
      }
      window.location.reload();
    }
    async function fetchAnotherBatch() {
      const statusNode = document.getElementById("fetch-status");
      if (statusNode) {
        statusNode.textContent = "Fetching another batch...";
      }
      const response = await fetch("/api/fetch-batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not fetch another batch.";
        }
        return;
      }
      if (!payload.batch_id) {
        if (statusNode) {
          statusNode.textContent = "No new messages found.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Fetched ${payload.fetched_count} new messages into ${payload.batch_id}.`;
      }
      window.location.href = `/?batch_id=${encodeURIComponent(payload.batch_id)}`;
    }
    async function savePreference(card, preference) {
      const payload = {
        item_key: card.dataset.itemKey,
        preference
      };
      const response = await fetch(`/api/evaluations/${encodeURIComponent(card.dataset.evaluationId)}/preferences`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const errorPayload = await response.json();
        window.alert(errorPayload.error || "Failed to save evaluation preference.");
        return;
      }
      window.location.reload();
    }
    async function runShadowEvaluation() {
      const statusNode = document.getElementById("fetch-status");
      if (statusNode) {
        statusNode.textContent = "Running OpenAI comparison over 100 reviewed messages...";
      }
      const response = await fetch("/api/evaluations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not run OpenAI comparison.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Saved ${payload.evaluation_id} with ${payload.comparison_count} disagreements to review.`;
      }
      window.location.href = `/?evaluation_id=${encodeURIComponent(payload.evaluation_id)}`;
    }
    async function runCandidateEvaluation() {
      const statusNode = document.getElementById("fetch-status");
      if (statusNode) {
        statusNode.textContent = "Running candidate evaluation over pending changes...";
      }
      const response = await fetch("/api/candidate-evaluations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not run candidate evaluation.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Saved candidate evaluation with ${payload.candidate_count} candidates. Batch recommendation: ${payload.batch_recommendation}.`;
      }
      window.location.reload();
    }
    async function decideCandidateChange(candidateId, decision, latestRecommendation) {
      const statusNode = document.getElementById("fetch-status");
      let overrideReason = "";
      if (decision === "override-promote") {
        overrideReason = window.prompt("Why are you promoting this despite the recommendation?", "Founder override after manual review") || "";
        if (!overrideReason) {
          if (statusNode) {
            statusNode.textContent = "Override promotion needs a reason.";
          }
          return;
        }
      }
      const response = await fetch(`/api/candidate-changes/${encodeURIComponent(candidateId)}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          actor: "browser-workbench",
          latest_recommendation: latestRecommendation || "",
          override_reason: overrideReason
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not save candidate decision.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Saved candidate decision for ${candidateId}.`;
      }
      window.location.reload();
    }
    function selectedTeachingMessageIds() {
      return [...document.querySelectorAll(".teach-example-checkbox:checked")].map((checkbox) => checkbox.dataset.messageId);
    }
    async function previewTeachingRule() {
      const statusNode = document.getElementById("fetch-status");
      const previewNode = document.getElementById("teaching-preview");
      const instructionNode = document.getElementById("teaching-instruction");
      const payload = {
        batch_id: "__BATCH_ID__",
        instruction: instructionNode ? instructionNode.value : "",
        message_ids: selectedTeachingMessageIds()
      };
      const response = await fetch("/api/teachable-rules/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not preview teaching rule.";
        }
        if (previewNode) {
          previewNode.textContent = responsePayload.error || "Could not preview teaching rule.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Previewed rule ${responsePayload.rule.id}: ${responsePayload.match_count} matches in this batch.`;
      }
      if (previewNode) {
        const matches = responsePayload.matches.map((match) => `${match.subject || match.message_id} -> ${match.labels_after.join(", ") || "(none)"}`);
        previewNode.innerHTML = `<strong>${responsePayload.match_count} matches in this batch</strong><div class="meta">${matches.length ? matches.join("<br>") : "No current batch emails matched."}</div>`;
      }
    }
    async function saveTeachingRule() {
      const statusNode = document.getElementById("fetch-status");
      const instructionNode = document.getElementById("teaching-instruction");
      const payload = {
        batch_id: "__BATCH_ID__",
        instruction: instructionNode ? instructionNode.value : "",
        message_ids: selectedTeachingMessageIds()
      };
      const response = await fetch("/api/teachable-rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not save teaching rule.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Saved teaching rule ${responsePayload.rule.id}. Reloading batch with saved-rule matches.`;
      }
      window.location.reload();
    }
    async function previewMemoryProposal() {
      const statusNode = document.getElementById("fetch-status");
      const previewNode = document.getElementById("teaching-preview");
      const explanationNode = document.getElementById("memory-proposal-explanation");
      const scopeNode = document.getElementById("memory-proposal-scope");
      const labelNode = document.getElementById("memory-proposal-label");
      const payload = {
        batch_id: "__BATCH_ID__",
        message_ids: selectedTeachingMessageIds(),
        scope: scopeNode ? scopeNode.value : "sender-cluster",
        label: labelNode ? labelNode.value : "newsletter",
        explanation: explanationNode ? explanationNode.value : ""
      };
      const response = await fetch("/api/memory-proposals/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not preview memory proposal.";
        }
        if (previewNode) {
          previewNode.textContent = responsePayload.error || "Could not preview memory proposal.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Prepared ${responsePayload.proposal.scope} memory proposal with ${responsePayload.proposal.preview.match_count} affected emails.`;
      }
      if (previewNode) {
        previewNode.dataset.proposalId = responsePayload.proposal.id;
        const matches = (responsePayload.proposal.preview.matches || []).map((match) => `${match.subject || match.message_id} -> ${match.labels_after.join(", ") || "(none)"}`);
        previewNode.innerHTML = `
          <strong>Proposal ready: ${escapeHtml(responsePayload.proposal.scope)} -> ${escapeHtml(responsePayload.proposal.label)}</strong>
          <div class="meta">Instruction: ${escapeHtml(responsePayload.proposal.instruction)}</div>
          <div class="meta">Preview matches: ${responsePayload.proposal.preview.match_count}</div>
          <div class="meta">${matches.length ? matches.join("<br>") : "No current stored emails matched."}</div>
        `;
      }
    }
    async function approveMemoryProposal() {
      const statusNode = document.getElementById("fetch-status");
      const previewNode = document.getElementById("teaching-preview");
      const proposalId = previewNode ? previewNode.dataset.proposalId : "";
      if (!proposalId) {
        if (statusNode) {
          statusNode.textContent = "Preview a memory proposal first.";
        }
        return;
      }
      const response = await fetch("/api/memory-proposals/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proposal_id: proposalId, notes: "Approved from browser workbench." })
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not approve memory proposal.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Approved memory proposal ${responsePayload.proposal.id}. Reloading batch.`;
      }
      window.location.reload();
    }
    async function rejectMemoryProposal() {
      const statusNode = document.getElementById("fetch-status");
      const previewNode = document.getElementById("teaching-preview");
      const proposalId = previewNode ? previewNode.dataset.proposalId : "";
      if (!proposalId) {
        if (statusNode) {
          statusNode.textContent = "Preview a memory proposal first.";
        }
        return;
      }
      const response = await fetch("/api/memory-proposals/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proposal_id: proposalId, notes: "Rejected from browser workbench." })
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not reject memory proposal.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Rejected memory proposal ${responsePayload.proposal.id}.`;
      }
      if (previewNode) {
        previewNode.dataset.proposalId = "";
      }
    }
    async function previewSafetyDisposition() {
      const statusNode = document.getElementById("fetch-status");
      const previewNode = document.getElementById("safety-preview");
      const explanationNode = document.getElementById("safety-disposition-explanation");
      const scopeNode = document.getElementById("safety-disposition-scope");
      const dispositionNode = document.getElementById("safety-disposition-value");
      const payload = {
        batch_id: "__BATCH_ID__",
        message_ids: selectedTeachingMessageIds(),
        scope: scopeNode ? scopeNode.value : "sender-cluster",
        disposition: dispositionNode ? dispositionNode.value : "phishing",
        explanation: explanationNode ? explanationNode.value : ""
      };
      const response = await fetch("/api/safety-dispositions/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not preview safety disposition.";
        }
        if (previewNode) {
          previewNode.textContent = responsePayload.error || "Could not preview safety disposition.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Prepared ${responsePayload.disposition.disposition} safety disposition with ${responsePayload.disposition.preview.match_count} affected emails.`;
      }
      if (previewNode) {
        previewNode.dataset.dispositionId = responsePayload.disposition.id;
        const exampleSenders = [...new Set((responsePayload.disposition.source_examples || []).map((example) => example.sender).filter(Boolean))];
        const signalTerms = responsePayload.disposition.match_signals || {};
        const signalSummary = [
          ...(signalTerms.subject_terms || []),
          ...(signalTerms.content_terms || [])
        ].slice(0, 8);
        const matches = (responsePayload.disposition.preview.matches || []).map((match) => {
          const sender = match.sender ? `${match.sender} - ` : "";
          return `${sender}${match.subject || match.message_id}`;
        });
        previewNode.innerHTML = `
          <strong>Safety review ready: ${escapeHtml(responsePayload.disposition.disposition)}</strong>
          <div class="meta">Scope: ${escapeHtml(responsePayload.disposition.scope)}</div>
          <div class="meta">Provider/account: ${escapeHtml(responsePayload.disposition.provider)} / ${escapeHtml(responsePayload.disposition.account_id || "(none)")}</div>
          <div class="meta">Examples: ${exampleSenders.length ? exampleSenders.map(escapeHtml).join(", ") : "(none)"}</div>
          <div class="meta">Signals: ${signalSummary.length ? signalSummary.map(escapeHtml).join(", ") : "(none)"}</div>
          <div class="meta">Why: ${escapeHtml(responsePayload.disposition.explanation || "No explanation provided.")}</div>
          <div class="meta">Preview matches: ${responsePayload.disposition.preview.match_count}</div>
          <div class="meta">${matches.length ? matches.join("<br>") : "No current stored emails matched."}</div>
        `;
      }
    }
    async function approveSafetyDisposition() {
      const statusNode = document.getElementById("fetch-status");
      const previewNode = document.getElementById("safety-preview");
      const dispositionId = previewNode ? previewNode.dataset.dispositionId : "";
      if (!dispositionId) {
        if (statusNode) {
          statusNode.textContent = "Preview a safety disposition first.";
        }
        return;
      }
      const response = await fetch("/api/safety-dispositions/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ disposition_id: dispositionId, notes: "Approved from browser workbench." })
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not approve safety disposition.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Approved safety disposition ${responsePayload.disposition.id}.`;
      }
      if (previewNode) {
        previewNode.dataset.dispositionId = responsePayload.disposition.id;
      }
    }
    async function rejectSafetyDisposition() {
      const statusNode = document.getElementById("fetch-status");
      const previewNode = document.getElementById("safety-preview");
      const dispositionId = previewNode ? previewNode.dataset.dispositionId : "";
      if (!dispositionId) {
        if (statusNode) {
          statusNode.textContent = "Preview a safety disposition first.";
        }
        return;
      }
      const response = await fetch("/api/safety-dispositions/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ disposition_id: dispositionId, notes: "Rejected from browser workbench." })
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not reject safety disposition.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Rejected safety disposition ${responsePayload.disposition.id}.`;
      }
      if (previewNode) {
        previewNode.dataset.dispositionId = "";
      }
    }
    async function disableTeachableRule(ruleId) {
      const statusNode = document.getElementById("fetch-status");
      const reason = window.prompt("Reason for disabling this saved rule?", "Too broad");
      if (reason === null) {
        return;
      }
      const response = await fetch(`/api/teachable-rules/${encodeURIComponent(ruleId)}/disable`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason })
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not disable rule.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Disabled saved rule ${payload.rule.id}. Reloading batch.`;
      }
      window.location.reload();
    }
    async function saveUnsubscribeSelections() {
      const statusNode = document.getElementById("fetch-status");
      const candidateCheckboxes = [...document.querySelectorAll(".unsubscribe-checkbox")];
      const payload = {
        candidate_keys: candidateCheckboxes.map((checkbox) => checkbox.dataset.candidateKey),
        selected_candidate_keys: candidateCheckboxes
          .filter((checkbox) => checkbox.checked)
          .map((checkbox) => checkbox.dataset.candidateKey)
      };
      const response = await fetch("/api/unsubscribe-candidates/selections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not save unsubscribe selections.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Saved ${responsePayload.saved_count} unsubscribe selections locally.`;
      }
      window.alert(`Saved ${responsePayload.saved_count} unsubscribe selections locally.`);
      window.location.reload();
    }
    async function previewUnsubscribeExecution() {
      const statusNode = document.getElementById("fetch-status");
      const response = await fetch("/api/unsubscribe-executions/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not preview unsubscribe execution.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Preview: ${payload.ready_count} ready, ${payload.unsupported_count} unsupported.`;
      }
      window.alert(`Execution preview:\nReady now: ${payload.ready_count}\nManual follow-up: ${payload.unsupported_count}`);
    }
    async function executeUnsubscribes() {
      const confirmation = window.prompt("Type UNSUBSCRIBE to execute supported selected unsubscribes.");
      if (confirmation === null) {
        return;
      }
      const statusNode = document.getElementById("fetch-status");
      const response = await fetch("/api/unsubscribe-executions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation })
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not execute unsubscribes.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Executed ${payload.executed_count} selected unsubscribes. ${payload.unsupported_count} require manual follow-up.`;
      }
      window.alert(`Execution complete:\nExecuted: ${payload.executed_count}\nManual follow-up: ${payload.unsupported_count}\nFailed: ${payload.failed_count}`);
      window.location.reload();
    }
    async function refreshUnifiedReviewQueue() {
      const statusNode = document.getElementById("fetch-status");
      if (statusNode) {
        statusNode.textContent = "Refreshing unified review queue...";
      }
      const response = await fetch("/api/unified-review-queue/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not refresh unified review queue.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Unified queue refreshed. Pending now: ${payload.summary.pending_count || 0}.`;
      }
      window.location.reload();
    }
    async function refreshOperationalReadiness() {
      const statusNode = document.getElementById("fetch-status");
      if (statusNode) {
        statusNode.textContent = "Refreshing operational readiness...";
      }
      const response = await fetch("/api/operational-readiness/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not refresh operational readiness.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Operational readiness refreshed: ${payload.overall_status}.`;
      }
      window.location.reload();
    }
    async function reviewUnifiedQueueItem(itemId, action, extraPayload = {}) {
      const statusNode = document.getElementById("fetch-status");
      if (statusNode) {
        statusNode.textContent = `Submitting ${action} for ${itemId}...`;
      }
      const response = await fetch(`/api/unified-review-queue/items/${encodeURIComponent(itemId)}/actions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...extraPayload })
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not apply queue action.";
        }
        return;
      }
      if (statusNode) {
        const pending = payload.queue_summary ? payload.queue_summary.pending_count : null;
        statusNode.textContent = pending === null
          ? `Applied ${action} for ${itemId}.`
          : `Applied ${action} for ${itemId}. Pending now: ${pending}.`;
      }
      window.location.reload();
    }
    const fetchBatchButton = document.getElementById("fetch-batch");
    if (fetchBatchButton) {
      fetchBatchButton.addEventListener("click", fetchAnotherBatch);
    }
    const refreshUnifiedReviewQueueButton = document.getElementById("refresh-unified-review-queue");
    if (refreshUnifiedReviewQueueButton) {
      refreshUnifiedReviewQueueButton.addEventListener("click", refreshUnifiedReviewQueue);
    }
    const refreshOperationalReadinessButton = document.getElementById("refresh-operational-readiness");
    if (refreshOperationalReadinessButton) {
      refreshOperationalReadinessButton.addEventListener("click", refreshOperationalReadiness);
    }
    const runShadowEvalButton = document.getElementById("run-shadow-eval");
    if (runShadowEvalButton) {
      runShadowEvalButton.addEventListener("click", runShadowEvaluation);
    }
    const runCandidateEvalButton = document.getElementById("run-candidate-eval");
    if (runCandidateEvalButton) {
      runCandidateEvalButton.addEventListener("click", runCandidateEvaluation);
    }
    const saveUnsubscribeButton = document.getElementById("save-unsubscribe-selections");
    if (saveUnsubscribeButton) {
      saveUnsubscribeButton.addEventListener("click", saveUnsubscribeSelections);
    }
    const previewUnsubscribeButton = document.getElementById("preview-unsubscribe-execution");
    if (previewUnsubscribeButton) {
      previewUnsubscribeButton.addEventListener("click", previewUnsubscribeExecution);
    }
    const executeUnsubscribeButton = document.getElementById("execute-unsubscribes");
    if (executeUnsubscribeButton) {
      executeUnsubscribeButton.addEventListener("click", executeUnsubscribes);
    }
    const previewTeachingButton = document.getElementById("preview-teaching-rule");
    if (previewTeachingButton) {
      previewTeachingButton.addEventListener("click", previewTeachingRule);
    }
    const saveTeachingButton = document.getElementById("save-teaching-rule");
    if (saveTeachingButton) {
      saveTeachingButton.addEventListener("click", saveTeachingRule);
    }
    const previewMemoryProposalButton = document.getElementById("preview-memory-proposal");
    if (previewMemoryProposalButton) {
      previewMemoryProposalButton.addEventListener("click", previewMemoryProposal);
    }
    const approveMemoryProposalButton = document.getElementById("approve-memory-proposal");
    if (approveMemoryProposalButton) {
      approveMemoryProposalButton.addEventListener("click", approveMemoryProposal);
    }
    const rejectMemoryProposalButton = document.getElementById("reject-memory-proposal");
    if (rejectMemoryProposalButton) {
      rejectMemoryProposalButton.addEventListener("click", rejectMemoryProposal);
    }
    const previewSafetyDispositionButton = document.getElementById("preview-safety-disposition");
    if (previewSafetyDispositionButton) {
      previewSafetyDispositionButton.addEventListener("click", previewSafetyDisposition);
    }
    const approveSafetyDispositionButton = document.getElementById("approve-safety-disposition");
    if (approveSafetyDispositionButton) {
      approveSafetyDispositionButton.addEventListener("click", approveSafetyDisposition);
    }
    const rejectSafetyDispositionButton = document.getElementById("reject-safety-disposition");
    if (rejectSafetyDispositionButton) {
      rejectSafetyDispositionButton.addEventListener("click", rejectSafetyDisposition);
    }
    for (const button of document.querySelectorAll(".disable-rule")) {
      button.addEventListener("click", () => disableTeachableRule(button.dataset.ruleId));
    }
    for (const button of document.querySelectorAll(".queue-action")) {
      button.addEventListener("click", () => reviewUnifiedQueueItem(button.dataset.itemId, button.dataset.action));
    }
    for (const button of document.querySelectorAll(".queue-answer")) {
      button.addEventListener("click", () => reviewUnifiedQueueItem(
        button.dataset.itemId,
        "answer",
        { answer_key: button.dataset.answerKey }
      ));
    }
    for (const button of document.querySelectorAll(".candidate-decision")) {
      button.addEventListener("click", () => decideCandidateChange(
        button.dataset.candidateId,
        button.dataset.decision,
        button.dataset.latestRecommendation
      ));
    }
    for (const button of document.querySelectorAll(".taxonomy-option")) {
      button.addEventListener("click", () => button.classList.toggle("active"));
    }
    for (const card of document.querySelectorAll(".item")) {
      const actionabilityButtons = card.querySelectorAll(".actionability-option");
      for (const button of actionabilityButtons) {
        button.addEventListener("click", () => {
          for (const option of actionabilityButtons) {
            option.classList.remove("active");
          }
          button.classList.add("active");
        });
      }
    }
    for (const card of document.querySelectorAll(".item")) {
      const approveButton = card.querySelector(".approve");
      const saveButton = card.querySelector(".save");
      const unlabeledButton = card.querySelector(".unlabeled");
      const rejectButton = card.querySelector(".reject");
      if (!approveButton || !saveButton || !unlabeledButton || !rejectButton) {
        continue;
      }
      approveButton.addEventListener("click", () => saveDecision(card, "approve"));
      saveButton.addEventListener("click", () => saveDecision(card, "edit"));
      unlabeledButton.addEventListener("click", () => {
        for (const option of card.querySelectorAll(".taxonomy-option")) {
          option.classList.remove("active");
        }
        saveDecision(card, "edit");
      });
      rejectButton.addEventListener("click", () => saveDecision(card, "reject"));
    }
    for (const card of document.querySelectorAll(".comparison-item")) {
      const reviewedButton = card.querySelector(".prefer-reviewed");
      const openaiButton = card.querySelector(".prefer-openai");
      if (!reviewedButton || !openaiButton) {
        continue;
      }
      reviewedButton.addEventListener("click", () => savePreference(card, "reviewed"));
      openaiButton.addEventListener("click", () => savePreference(card, "openai"));
    }
  </script>
</body>
</html>""".replace("__BATCH_ID__", escape(batch_id)).replace("__HEADING__", escape(heading)).replace(
            "__SUBHEADING__", escape(subheading)
        ).replace("__BODY_HTML__", body_html)

    def _render_workbench(self) -> str:
        operational_readiness_html = self._render_operational_readiness_panel()
        unified_queue_html = self._render_unified_review_queue_panel()
        candidate_change_html = self._render_candidate_change_panel()
        reminder_html = self._render_threshold_reminders()
        trusted_sender_html = self._render_trusted_sender_summary()
        unsubscribe_inventory_html = self._render_unsubscribe_inventory()
        shadow_eval_html = self._render_shadow_eval_summary()
        batch_cards = "".join(self._render_batch_card(summary) for summary in self._list_batch_summaries())
        if not batch_cards:
            batch_cards = '<div class="meta">No stored batches found yet.</div>'
        return (
            operational_readiness_html
            + unified_queue_html
            + candidate_change_html
            + '<section class="panel"><h2>Workbench actions</h2>'
            '<div class="actions">'
            '<button type="button" class="action" id="fetch-batch">Fetch another batch</button>'
            '<button type="button" class="action secondary" id="run-shadow-eval">Run OpenAI comparison for 100 reviewed messages</button>'
            '</div>'
            '<p class="meta">The OpenAI comparison sends stored reviewed message content to OpenAI only when you trigger it explicitly.</p>'
            '</section>'
            + reminder_html
            + trusted_sender_html
            + unsubscribe_inventory_html
            + shadow_eval_html
            + '<section class="panel">'
            '<h2>Stored batches</h2>'
            '<div class="items">'
            f"{batch_cards}"
            "</div>"
            "</section>"
        )

    def _render_operational_readiness_panel(self) -> str:
        try:
            report = self._load_operational_readiness()
        except Exception as exc:
            return (
                '<section class="panel error-panel"><h2>Operational Readiness</h2>'
                f'<p class="meta">Could not load readiness report: {escape(str(exc))}</p></section>'
            )
        summary = report.get("summary", {})
        status = report.get("overall_status", "WARN")
        progress = report.get("progress", {})
        reasons_html = "".join(f'<li>{escape(reason)}</li>' for reason in report.get("reasons", []))
        runs_html = "".join(
            '<div class="field">'
            f'<strong>{escape(run.get("run_id", ""))}</strong> '
            f'<span class="pill">{run.get("unresolved_rate", 0) * 100:.2f}% unresolved</span> '
            f'<span class="meta">{run.get("caution_rate", 0) * 100:.2f}% caution</span>'
            '</div>'
            for run in report.get("runs", [])[:5]
        ) or '<p class="meta">No recent runs available.</p>'
        return (
            '<section class="panel">'
            '<h2>Operational Readiness</h2>'
            '<p class="meta">This is the day-to-day trust check for the recent loop: healthy, shaky, or stop.</p>'
            '<div class="summary-grid">'
            f'<div class="metric"><strong>{escape(status)}</strong><div class="meta">Current status</div></div>'
            f'<div class="metric"><strong>{summary.get("latest_unresolved_rate", 0) * 100:.2f}%</strong><div class="meta">Latest unresolved</div></div>'
            f'<div class="metric"><strong>{summary.get("latest_queue_pending_count", 0)}</strong><div class="meta">Queue debt</div></div>'
            f'<div class="metric"><strong>{summary.get("founder_resolved_gain_total", 0)}</strong><div class="meta">Founder resolved gain</div></div>'
            '</div>'
            f'<p class="meta">Progress to target: {progress.get("unresolved_current_count", 0)}/'
            f'{progress.get("unresolved_target_count", 0)} unresolved target on the latest corpus. '
            f'Remaining gap: {progress.get("unresolved_remaining_gap_count", 0)} messages. '
            f'Founder questions: {progress.get("founder_question_count", 0)}/'
            f'{progress.get("founder_question_limit", 0)}.</p>'
            '<div class="actions">'
            '<button type="button" class="action secondary" id="refresh-operational-readiness">Refresh readiness</button>'
            '</div>'
            f'<ul>{reasons_html}</ul>'
            f'{runs_html}'
            '</section>'
        )

    def _render_candidate_change_panel(self) -> str:
        candidates = self._list_candidate_changes()
        if not candidates:
            return (
                '<section class="panel"><h2>Candidate Change Review</h2>'
                '<p class="meta">No candidate changes are stored yet. Future-rule teaching candidates and broader change proposals will appear here for evaluation before promotion.</p>'
                '</section>'
            )
        pending_like = [
            candidate for candidate in candidates if candidate.get("status") not in {"promoted", "rejected", "override-promoted"}
        ]
        promoted_count = sum(1 for candidate in candidates if candidate.get("status") in {"promoted", "override-promoted"})
        recommended_count = sum(1 for candidate in candidates if str(candidate.get("status", "")).startswith("recommended-"))
        cards = "".join(self._render_candidate_change_card(candidate) for candidate in candidates[:10])
        return (
            '<section class="panel">'
            '<h2>Candidate Change Review</h2>'
            '<p class="meta">This is the eval-and-promote lane for future rules and bigger change candidates. Candidates are evaluated first, then either promoted, kept pending, rejected, or override-promoted with an audit reason.</p>'
            '<div class="summary-grid">'
            f'<div class="metric"><strong>{len(pending_like)}</strong><div class="meta">Pending review</div></div>'
            f'<div class="metric"><strong>{recommended_count}</strong><div class="meta">With recommendation</div></div>'
            f'<div class="metric"><strong>{promoted_count}</strong><div class="meta">Promoted</div></div>'
            '</div>'
            '<div class="actions">'
            '<button type="button" class="action secondary" id="run-candidate-eval">Run candidate evaluation</button>'
            '</div>'
            '<div class="items">'
            f'{cards}'
            '</div>'
            '</section>'
        )

    def _render_candidate_change_card(self, candidate: dict) -> str:
        latest_recommendation = candidate.get("latest_recommendation") or "Not yet evaluated"
        source_refs = candidate.get("source_refs") or []
        decision_fields = ""
        if candidate.get("status") not in {"promoted", "rejected", "override-promoted"}:
            decision_fields = (
                '<div class="actions">'
                f'<button type="button" class="action candidate-decision" data-candidate-id="{escape(candidate["id"])}" data-decision="promote" data-latest-recommendation="{escape(latest_recommendation)}">Promote</button>'
                f'<button type="button" class="action secondary candidate-decision" data-candidate-id="{escape(candidate["id"])}" data-decision="keep-pending" data-latest-recommendation="{escape(latest_recommendation)}">Keep pending</button>'
                f'<button type="button" class="action secondary candidate-decision" data-candidate-id="{escape(candidate["id"])}" data-decision="reject" data-latest-recommendation="{escape(latest_recommendation)}">Reject</button>'
                f'<button type="button" class="action secondary candidate-decision" data-candidate-id="{escape(candidate["id"])}" data-decision="override-promote" data-latest-recommendation="{escape(latest_recommendation)}">Override promote</button>'
                '</div>'
            )
        audit_html = ""
        if candidate.get("decision_actor") or candidate.get("override_reason"):
            audit_html = (
                f'<div class="field"><strong>Decided by:</strong> {escape(candidate.get("decision_actor") or "(missing)")}</div>'
                f'<div class="field"><strong>Why:</strong> {escape(candidate.get("override_reason") or "(none)")}</div>'
            )
        return (
            '<article class="item">'
            f'<div class="field"><strong>Title:</strong> {escape(candidate.get("title") or "(missing)")}</div>'
            f'<div class="field"><strong>Status:</strong> {escape(candidate.get("status") or "(missing)")} <span class="pill">{escape(latest_recommendation)}</span></div>'
            f'<div class="field"><strong>Kind:</strong> {escape(candidate.get("kind") or "(missing)")}</div>'
            f'<div class="field"><strong>Source:</strong> {escape(candidate.get("source") or "(missing)")}</div>'
            f'<div class="field"><strong>Scope:</strong> {escape(candidate.get("affected_scope_summary") or "(missing)")}</div>'
            f'<div class="field"><strong>Description:</strong> {escape(candidate.get("description") or "(none)")}</div>'
            f'<div class="field"><strong>Evidence refs:</strong> {len(source_refs)}</div>'
            f'<div class="field"><strong>Latest eval:</strong> {escape(candidate.get("latest_evaluation_ref") or "(none)")}</div>'
            f'{audit_html}'
            f'{decision_fields}'
            '</article>'
        )

    def _list_candidate_changes(self) -> list[dict]:
        if not hasattr(self, "_candidate_store"):
            return []
        candidates = [candidate.to_dict() for candidate in self._candidate_store.list_candidates()]
        return sorted(
            candidates,
            key=lambda candidate: (
                1 if candidate.get("status") not in {"promoted", "rejected", "override-promoted"} else 0,
                candidate.get("updated_at", ""),
                candidate.get("id", ""),
            ),
            reverse=True,
        )

    def _render_unified_review_queue_panel(self) -> str:
        try:
            queue = self._load_or_build_unified_review_queue()
        except Exception as exc:
            return (
                '<section class="panel error-panel"><h2>Unified Review Queue</h2>'
                f'<p class="meta">Could not load queue: {escape(str(exc))}</p></section>'
            )
        summary = queue.get("summary", {})
        top_items = [item for item in queue.get("items", []) if item.get("status") == "pending"][:10]
        metrics = (
            '<div class="summary-grid">'
            f'<div class="metric"><strong>{summary.get("pending_count", 0)}</strong><div class="meta">Pending now</div></div>'
            f'<div class="metric"><strong>{summary.get("pending_by_type", {}).get("founder-question", 0)}</strong><div class="meta">Founder questions</div></div>'
            f'<div class="metric"><strong>{summary.get("pending_by_type", {}).get("runtime-llm-candidate", 0)}</strong><div class="meta">Runtime LLM candidates</div></div>'
            f'<div class="metric"><strong>{summary.get("pending_by_type", {}).get("safety-disposition", 0)}</strong><div class="meta">Safety decisions</div></div>'
            '</div>'
        )
        if not top_items:
            items_html = '<p class="meta">No pending queue items right now.</p>'
        else:
            items_html = '<div class="items">' + "".join(self._render_unified_review_queue_item(item) for item in top_items) + "</div>"
        provider_counts = summary.get("provider_counts", {})
        provider_pills = "".join(
            f'<span class="pill">{escape(provider)}: {count}</span>'
            for provider, count in provider_counts.items()
        ) or '<span class="meta">No provider pressure recorded yet.</span>'
        return (
            '<section class="panel">'
            '<h2>Unified Review Queue</h2>'
            '<p class="meta">This is now the main multi-inbox teaching loop. It ranks founder questions, safety work, runtime model candidates, and memory proposals in one place.</p>'
            f'{metrics}'
            f'<div style="margin-top: 12px;">{provider_pills}</div>'
            '<div class="actions">'
            '<button type="button" class="action secondary" id="refresh-unified-review-queue">Refresh queue</button>'
            '</div>'
            f'{items_html}'
            '</section>'
        )

    def _render_unified_review_queue_item(self, item: dict) -> str:
        rank = item.get("rank", {})
        summary = item.get("summary", {})
        question = item.get("decision_payload", {}).get("question", {})
        reasons_html = "".join(f'<li>{escape(reason)}</li>' for reason in rank.get("reasons", []))
        suggested_labels = summary.get("suggested_labels") or []
        prompt_html = ""
        if question.get("prompt"):
            prompt_html = f'<div class="field"><strong>Prompt:</strong> {escape(question.get("prompt", ""))}</div>'
        answer_buttons = ""
        if item.get("item_type") == "founder-question":
            question = item.get("decision_payload", {}).get("question", {})
            answer_buttons = "".join(
                f'<button type="button" class="action secondary queue-answer" '
                f'data-item-id="{escape(item["item_id"])}" '
                f'data-answer-key="{escape(option.get("answer_key", ""))}">{escape(option.get("description", option.get("answer_key", "Answer")))}</button>'
                for option in question.get("answer_options", [])[:3]
            )
        action_buttons = ""
        if item.get("item_type") == "founder-question":
            action_buttons = answer_buttons
        else:
            action_buttons = (
                f'<button type="button" class="action queue-action" data-item-id="{escape(item["item_id"])}" data-action="approve">Approve</button>'
                f'<button type="button" class="action secondary queue-action" data-item-id="{escape(item["item_id"])}" data-action="reject">Reject</button>'
            )
        rendered_labels = ", ".join(gmail_label_name(label) for label in suggested_labels) if suggested_labels else "(none)"
        return (
            '<article class="item">'
            f'<div class="field"><strong>Priority:</strong> {rank.get("score", 0)} '
            f'<span class="pill">{escape(rank.get("lane", "review"))}</span></div>'
            f'<div class="field"><strong>Type:</strong> {escape(item.get("item_type", ""))}</div>'
            f'<div class="field"><strong>Provider:</strong> {escape(item.get("provider", "") or "(mixed)")}</div>'
            f'<div class="field"><strong>Title:</strong> {escape(item.get("title", ""))}</div>'
            f'<div class="field"><strong>Suggested labels:</strong> {escape(rendered_labels)}</div>'
            f'{prompt_html}'
            f'<div class="field"><strong>Impact:</strong> {escape(_queue_item_impact_text(item))}</div>'
            f'<ul>{reasons_html}</ul>'
            f'<div class="actions">{action_buttons}</div>'
            '</article>'
        )

    def _list_batch_summaries(self) -> list[dict]:
        batch_paths = sorted((self._storage_dir / "batches").glob("*.json"))
        return [summarize_batch(self._storage_dir, load_batch(batch_path)) for batch_path in batch_paths]

    def _render_batch_card(self, summary: dict) -> str:
        if summary["review_states"].get("pending", 0) > 0:
            status = "Pending review"
        elif summary["review_states"].get("reviewed", 0) == summary["item_count"]:
            status = "Reviewed"
        else:
            status = "Not started"
        return (
            '<article class="item">'
            f'<div class="field"><strong>Batch:</strong> {escape(summary["batch_id"])}</div>'
            f'<div class="field"><strong>Status:</strong> {escape(status)}</div>'
            f'<div class="field"><strong>Items:</strong> {summary["item_count"]}</div>'
            f'<div class="field"><strong>Reviewed:</strong> {summary["review_states"].get("reviewed", 0)}</div>'
            f'<div class="field"><strong>Remaining:</strong> {summary["review_states"].get("pending", 0)}</div>'
            f'<div class="field"><a href="/?batch_id={escape(summary["batch_id"])}">Open batch</a></div>'
            "</article>"
        )

    def _render_threshold_reminders(self) -> str:
        reviewed_count = self._cumulative_reviewed_count()
        sections = []
        if reviewed_count >= 50:
            sections.append(f"<p>{escape(f'{reviewed_count} reviewed messages reached. 50-message checkpoint is ready.')}</p>")
        if reviewed_count >= 100:
            sections.append(self._render_low_value_gate_summary(reviewed_count))
        if reviewed_count >= 200:
            sections.append("<p>200-message confidence checkpoint reached.</p>")
        if not sections:
            return ""
        reminder_items = "".join(sections)
        return f'<section class="panel"><h2>Review checkpoints</h2>{reminder_items}</section>'

    def _render_trusted_sender_summary(self) -> str:
        store = TrustedSenderStore(self._storage_dir)
        entries = store.load_entries_or_rebuild()
        path = self._storage_dir / "trusted_personal_senders.json"
        if not entries:
            body = (
                '<p class="meta">No trusted personal senders are seeded yet.</p>'
                '<p class="meta">The file is kept at '
                f'{escape(str(path))}'
                ' and will populate automatically from repeated reviewed personal mail or future manual approvals.</p>'
            )
        else:
            rows = "".join(
                '<article class="item">'
                f'<div class="field"><strong>Address:</strong> {escape(entry["address"])}</div>'
                f'<div class="field"><strong>Source:</strong> {escape(entry.get("source", "unknown"))}</div>'
                f'<div class="field"><strong>Kind:</strong> {escape(entry.get("kind", "direct"))}</div>'
                f'<div class="field"><strong>Notes:</strong> {escape(entry.get("notes", ""))}</div>'
                '</article>'
                for entry in entries
            )
            body = (
                f'<p class="meta">Allowlist file: {escape(str(path))}</p>'
                '<div class="items">'
                f'{rows}'
                '</div>'
            )
        return f'<section class="panel"><h2>Trusted Personal Senders</h2>{body}</section>'

    def _render_shadow_eval_summary(self) -> str:
        evaluation_paths = sorted(
            [
                path
                for path in (self._storage_dir / "evaluations").glob("shadow-label-eval-*.json")
                if not path.stem.endswith("-preferences")
            ],
            reverse=True,
        )
        if not evaluation_paths:
            return (
                '<section class="panel"><h2>Shadow Evaluations</h2>'
                '<p class="meta">No shadow evaluation reports found yet.</p></section>'
            )

        cards = []
        for path in evaluation_paths[:5]:
            report = json.loads(path.read_text())
            eval_id = path.stem
            comparison_count = len(report.get("comparison_candidates", []))
            cards.append(
                '<article class="item">'
                f'<div class="field"><strong>Evaluation:</strong> {escape(eval_id)}</div>'
                f'<div class="field"><strong>Reviewed:</strong> {report["overall"]["reviewed_count"]}</div>'
                f'<div class="field"><strong>Heuristic exact-match:</strong> {report["overall"]["heuristic"]["exact_match_rate"]}%</div>'
                f'<div class="field"><strong>OpenAI vs your final result:</strong> {comparison_count}</div>'
                f'<div class="field"><a href="/?evaluation_id={escape(eval_id)}">Open evaluation</a></div>'
                '</article>'
            )
        return (
            '<section class="panel"><h2>Shadow Evaluations</h2>'
            '<div class="items">'
            f'{"".join(cards)}'
            '</div></section>'
        )

    def _render_unsubscribe_inventory(self) -> str:
        candidates = self._unsubscribe_store.list_candidates()
        if not candidates:
            return (
                '<section class="panel"><h2>Unsubscribe inventory</h2>'
                '<p class="meta">No unsubscribe candidates have been detected in stored batches yet.</p>'
                '</section>'
            )

        selected_count = sum(1 for candidate in candidates if candidate.get("decision_state") == "selected")
        execution_preview = self._unsubscribe_executor.preview_selected_candidates()
        cards = "".join(self._render_unsubscribe_candidate_card(candidate) for candidate in candidates)
        return (
            '<section class="panel"><h2>Unsubscribe inventory</h2>'
            '<p class="meta">Review mailing-list candidates from stored batches only. '
            'Selections are saved locally for a later execution slice. No unsubscribe actions run here.</p>'
            f'<p class="meta">Selected for later unsubscribe: {selected_count} of {len(candidates)}</p>'
            '<section class="panel">'
            '<h3>Execution preview</h3>'
            '<div class="summary-grid">'
            f'<div class="metric"><strong>{execution_preview["ready_count"]}</strong><div class="meta">Ready now</div></div>'
            f'<div class="metric"><strong>{execution_preview["unsupported_count"]}</strong><div class="meta">Manual follow-up</div></div>'
            f'<div class="metric"><strong>{execution_preview["selected_count"]}</strong><div class="meta">Selected total</div></div>'
            '</div>'
            '</section>'
            '<div class="actions">'
            '<button type="button" class="action secondary" id="save-unsubscribe-selections">Save unsubscribe selections</button>'
            '<button type="button" class="action secondary" id="preview-unsubscribe-execution">Preview execution</button>'
            '<button type="button" class="action" id="execute-unsubscribes">Execute supported unsubscribes</button>'
            '</div>'
            '<div class="items">'
            f'{cards}'
            '</div></section>'
        )

    def _render_unsubscribe_candidate_card(self, candidate: dict) -> str:
        checked = " checked" if candidate.get("decision_state") == "selected" else ""
        reason_text = ", ".join(candidate.get("qualification_reasons") or []) or "(missing)"
        execution_preview = self._unsubscribe_executor._build_preview_item(candidate)
        state_label = {
            "selected": "Selected for later unsubscribe",
            "not_selected": "Kept off the unsubscribe list",
            "undecided": "Undecided",
        }.get(candidate.get("decision_state"), "Undecided")
        latest_execution = candidate.get("latest_execution")
        latest_execution_html = ""
        if latest_execution:
            latest_execution_html = (
                f'<div class="field"><strong>Latest unsubscribe:</strong> '
                f'{escape(latest_execution.get("status") or "(missing)")} via '
                f'{escape(latest_execution.get("method") or "(missing)")}</div>'
                f'<div class="field"><strong>Notes:</strong> {escape(latest_execution.get("notes") or "(none)")}</div>'
            )
        manual_action_html = render_manual_unsubscribe_action(execution_preview)
        return (
            '<article class="item unsubscribe-row">'
            f'<input type="checkbox" class="checkbox unsubscribe-checkbox" data-candidate-key="{escape(candidate["list_key"])}"{checked}>'
            '<div>'
            f'<div class="field"><strong>List:</strong> {escape(candidate.get("display_name") or "(missing)")}</div>'
            f'<div class="field"><strong>Sender:</strong> {escape(candidate.get("sender") or "(missing)")}</div>'
            f'<div class="field"><strong>Provider:</strong> {escape(candidate.get("provider") or "(missing)")}</div>'
            f'<div class="field"><strong>Evidence:</strong> {candidate.get("evidence_count", 0)} messages</div>'
            f'<div class="field"><strong>Most recent:</strong> {escape(candidate.get("latest_message_date") or "(missing)")}</div>'
            f'<div class="field"><strong>Qualified because:</strong> {escape(reason_text)}</div>'
            f'<div class="field"><strong>State:</strong> {escape(state_label)}</div>'
            f'{latest_execution_html}'
            f'{manual_action_html}'
            '</div>'
            '</article>'
        )

    def _render_shadow_evaluation(self, evaluation_id: str) -> str:
        evaluation = self._load_evaluation(evaluation_id)
        items = evaluation.get("comparison_candidates", [])
        if not items:
            return (
                '<section class="panel"><h2>No OpenAI differences found.</h2>'
                '<p class="meta">This evaluation has no cases where OpenAI differed from your final reviewed result.</p></section>'
            )

        preference_counts = Counter(item.get("preference") for item in items if item.get("preference"))
        summary = (
            '<section class="panel"><h2>OpenAI vs Your Final Review</h2>'
            f'<p class="meta">You are choosing between your final reviewed result and the OpenAI shadow suggestion on {len(items)} differing messages.</p>'
            f'<p class="meta">Prefer your final reviewed result: {preference_counts.get("reviewed", 0)} | '
            f'Prefer OpenAI: {preference_counts.get("openai", 0)}</p>'
            '<p class="meta">Current system suggestion is shown only as background context. It is not one of the two choices.</p>'
            '</section>'
        )
        cards = "".join(self._render_shadow_eval_card(evaluation_id, item, index, len(items)) for index, item in enumerate(items, start=1))
        return summary + f'<section class="panel"><div class="items">{cards}</div></section>'

    def _render_shadow_eval_card(self, evaluation_id: str, item: dict, index: int, total_items: int) -> str:
        preview = preview_text(item)
        message_context = render_message_context(item)
        reviewed_labels = ", ".join(gmail_label_name(label) for label in item.get("ground_truth", [])) or "(unlabeled)"
        heuristic_labels = ", ".join(gmail_label_name(label) for label in item.get("heuristic_labels", [])) or "(unlabeled)"
        openai_labels = ", ".join(gmail_label_name(label) for label in item.get("model_labels", [])) or "(unlabeled)"
        item_key = f'{item["batch_id"]}:{item["message_id"]}'
        preference = item.get("preference")
        reviewed_class = " secondary" if preference == "reviewed" else ""
        openai_class = " secondary" if preference == "openai" else ""
        return (
            f'<article class="item comparison-item" data-evaluation-id="{escape(evaluation_id)}" data-item-key="{escape(item_key)}">'
            f'<div class="meta">Disagreement {index} of {total_items}</div>'
            f'<div class="field"><strong>Batch:</strong> {escape(item["batch_id"])}</div>'
            f'<div class="field"><strong>Message ID:</strong> {escape(item["message_id"])}</div>'
            f'<div class="field"><strong>From:</strong> {escape(item.get("sender") or "(missing)")}</div>'
            f'<div class="field"><strong>Subject:</strong> {escape(item.get("subject") or "(missing)")}</div>'
            f'<div class="field"><strong>Date:</strong> {escape(item.get("date") or "(missing)")}</div>'
            f'<div class="field"><strong>Preview:</strong> {escape(preview)}</div>'
            f"{message_context}"
            '<div class="compare-grid">'
            '<div class="compare-card">'
            '<h3>Current system suggestion (background only)</h3>'
            f'<div class="field"><strong>Labels:</strong> {escape(heuristic_labels)}</div>'
            '</div>'
            '<div class="compare-card">'
            '<h3>Your final reviewed result</h3>'
            f'<div class="field"><strong>Labels:</strong> {escape(reviewed_labels)}</div>'
            '</div>'
            '<div class="compare-card">'
            '<h3>OpenAI shadow suggestion</h3>'
            f'<div class="field"><strong>Labels:</strong> {escape(openai_labels)}</div>'
            f'<div class="field"><strong>Why:</strong> {escape(item.get("model_reason") or "(missing)")}</div>'
            '</div>'
            '</div>'
            '<p class="meta">Pick between your final reviewed result and OpenAI. The current system suggestion is shown only to help you understand the original miss.</p>'
            '<div class="actions">'
            f'<button type="button" class="action prefer-reviewed{reviewed_class}">Prefer your final reviewed result</button>'
            f'<button type="button" class="action prefer-openai{openai_class}">Prefer OpenAI</button>'
            '</div>'
            '</article>'
        )

    def _load_evaluation(self, evaluation_id: str) -> dict:
        report_path = self._storage_dir / "evaluations" / f"{evaluation_id}.json"
        if not report_path.exists():
            raise FileNotFoundError(evaluation_id)
        report = json.loads(report_path.read_text())
        preferences = self._load_evaluation_preferences(evaluation_id)
        for item in report.get("comparison_candidates", []):
            self._hydrate_evaluation_item(item, preferences)
        for item in report.get("disagreements", {}).get("model_better_than_heuristic", []):
            self._hydrate_evaluation_item(item, preferences)
        for item in report.get("disagreements", {}).get("heuristic_better_than_model", []):
            self._hydrate_evaluation_item(item, preferences)
        return report

    def _hydrate_evaluation_item(self, item: dict, preferences: dict[str, str]) -> None:
        item.update(self._lookup_batch_item_context(item["batch_id"], item["message_id"]))
        item_key = f'{item["batch_id"]}:{item["message_id"]}'
        item["preference"] = migrate_legacy_preference(preferences.get(item_key))

    def _lookup_batch_item_context(self, batch_id: str, message_id: str) -> dict:
        if self._batch_item_context_index is None:
            self._batch_item_context_index = self._build_batch_item_context_index()
        return self._batch_item_context_index.get((batch_id, message_id), {})

    def _build_batch_item_context_index(self) -> dict[tuple[str, str], dict]:
        index: dict[tuple[str, str], dict] = {}
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_batch(batch_path)
            batch_id = batch.get("batch_id")
            if not batch_id:
                continue
            for item in batch.get("items", []):
                message_id = item.get("message_id")
                if not message_id:
                    continue
                index[(batch_id, message_id)] = {
                    "date": item.get("date"),
                    "snippet": item.get("snippet"),
                    "body": item.get("body"),
                    "interpretation": item.get("interpretation"),
                }
        return index

    def _load_evaluation_preferences(self, evaluation_id: str) -> dict[str, str]:
        path = self._evaluation_preference_path(evaluation_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def _save_evaluation_preference(self, evaluation_id: str, payload: dict) -> dict:
        report_path = self._storage_dir / "evaluations" / f"{evaluation_id}.json"
        if not report_path.exists():
            raise FileNotFoundError(evaluation_id)
        preferences = self._load_evaluation_preferences(evaluation_id)
        preferences[payload["item_key"]] = payload["preference"]
        self._evaluation_preference_path(evaluation_id).write_text(json.dumps(preferences, indent=2))
        return {"preferences": preferences}

    def _evaluation_preference_path(self, evaluation_id: str):
        return self._storage_dir / "evaluations" / f"{evaluation_id}-preferences.json"

    def _cumulative_reviewed_count(self) -> int:
        reviewed_count = 0
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_batch(batch_path)
            reviewed_count += sum(1 for item in batch["items"] if item.get("review_state") == "reviewed")
        return reviewed_count

    def _render_low_value_gate_summary(self, reviewed_count: int) -> str:
        gate_stats = self._low_value_gate_stats()
        explicit_count = gate_stats["explicit_count"]
        safe_count = gate_stats["safe_count"]
        precision = round((safe_count / explicit_count) * 100) if explicit_count else 0
        return (
            f"<p>{reviewed_count}-message automation gate is ready for founder review.</p>"
            f"<p>Low-value actionability precision: {precision}%</p>"
            f"<p>{safe_count} of {explicit_count} explicitly reviewed low-value candidates marked safe to remove.</p>"
        )

    def _low_value_gate_stats(self) -> dict[str, int]:
        explicit_count = 0
        safe_count = 0
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_batch(batch_path)
            for item in batch["items"]:
                if item.get("review_state") != "reviewed":
                    continue
                if item.get("actionability") not in {"safe-to-remove-from-inbox", "keep-in-inbox"}:
                    continue
                final_labels = set(item.get("final_labels") or [])
                if not final_labels.intersection({"promotions", "spam-low-value"}):
                    continue
                explicit_count += 1
                if item.get("actionability") == "safe-to-remove-from-inbox":
                    safe_count += 1
        return {"explicit_count": explicit_count, "safe_count": safe_count}

    def _render_summary(self, summary: dict) -> str:
        label_pills = "".join(
            f'<span class="pill">{escape(label)}: {count}</span>'
            for label, count in summary["label_counts"].items()
        ) or '<span class="meta">No reviewed labels yet.</span>'
        return (
            '<section class="panel">'
            '<h2>Feedback summary</h2>'
            '<div class="summary-grid">'
            f'<div class="metric"><strong>{summary["total_items"]}</strong><div class="meta">Total items</div></div>'
            f'<div class="metric"><strong>{summary["reviewed_items"]}</strong><div class="meta">Reviewed</div></div>'
            f'<div class="metric"><strong>{summary["remaining_items"]}</strong><div class="meta">Remaining</div></div>'
            '</div>'
            f'<div style="margin-top: 12px;">{label_pills}</div>'
            '</section>'
        )

    def _render_pending_items(self, batch_id: str, pending_items: list[dict]) -> str:
        safety_contexts = _approved_safety_contexts_for_storage(self._storage_dir)
        pending_items = [_enriched_pending_item(item, safety_contexts) for item in pending_items]
        pending_items = _sorted_pending_items(pending_items)
        cards = "".join(
            self._render_pending_item_card(batch_id, index, len(pending_items), item)
            for index, item in enumerate(pending_items, start=1)
        )
        return (
            self._render_teaching_panel(batch_id)
            + self._render_safety_targets_panel(pending_items)
            + f'<section class="panel"><div class="items">{cards}</div></section>'
        )

    def _render_safety_targets_panel(self, pending_items: list[dict]) -> str:
        prioritized = [item for item in pending_items if item.get("safety_priority", {}).get("priority_score", 0) > 0][:5]
        if not prioritized:
            return ""
        rows = "".join(
            '<div class="field">'
            f'<strong>{escape(item.get("subject") or item["message_id"])}</strong> '
            f'<span class="pill safety-priority">score {item["safety_priority"]["priority_score"]}</span> '
            f'<span class="meta">{escape(item.get("sender") or "(missing)")}</span>'
            "</div>"
            for item in prioritized
        )
        return (
            '<section class="panel">'
            '<h2>Top Safety Targets</h2>'
            '<p class="meta">Approved safety memory and high-risk signals are pinned here first for batch review.</p>'
            f"{rows}"
            '</section>'
        )

    def _render_teaching_panel(self, batch_id: str) -> str:
        return (
            '<section class="panel">'
            '<h2>Teach classification from selected emails</h2>'
            '<div class="teaching-grid">'
            '<div>'
            '<textarea id="teaching-instruction" class="teaching-input" '
            'aria-label="Teaching instruction">anything from recruiters, Ashby, Greenhouse, or Lever should be job-related and kept visible</textarea>'
            '<div class="actions">'
            '<button type="button" class="action secondary" id="preview-teaching-rule">Preview rule</button>'
            '<button type="button" class="action" id="save-teaching-rule">Save rule</button>'
            '</div>'
            '<p class="meta">Select one or more pending email cards below, preview the local rule, then save it. '
            'Saved rules can add retrieval labels but cannot create low-value inbox-removal labels.</p>'
            '<hr style="margin: 16px 0; border: 0; border-top: 1px solid var(--line);">'
            '<h3 style="margin: 0 0 8px;">Propose durable memory from a correction</h3>'
            '<div class="teaching-subgrid">'
            '<select id="memory-proposal-scope" class="teaching-select" aria-label="Memory proposal scope">'
            '<option value="sender-cluster">This sender cluster</option>'
            '<option value="sender">This sender</option>'
            '<option value="global">Global preference</option>'
            '</select>'
            '<select id="memory-proposal-label" class="teaching-label-select" aria-label="Memory proposal label">'
            f'{"".join(f"<option value=\"{escape(label)}\">{escape(gmail_label_name(label))}</option>" for label in CANONICAL_LABEL_ORDER)}'
            '</select>'
            '</div>'
            '<textarea id="memory-proposal-explanation" class="teaching-input" '
            'aria-label="Memory proposal explanation" '
            'placeholder="Optional explanation. Required for global memory proposals."></textarea>'
            '<div class="actions">'
            '<button type="button" class="action secondary" id="preview-memory-proposal">Preview memory proposal</button>'
            '<button type="button" class="action" id="approve-memory-proposal">Approve memory proposal</button>'
            '<button type="button" class="action secondary" id="reject-memory-proposal">Reject proposal</button>'
            '</div>'
            '<p class="meta">This path creates a proposal first, shows affected emails, then writes durable memory only after approval.</p>'
            '<hr style="margin: 16px 0; border: 0; border-top: 1px solid var(--line);">'
            '<h3 style="margin: 0 0 8px;">Record a safety-lane disposition</h3>'
            '<div class="teaching-subgrid">'
            '<select id="safety-disposition-scope" class="teaching-select" aria-label="Safety disposition scope">'
            '<option value="sender-cluster">This sender cluster</option>'
            '<option value="sender">This sender</option>'
            '<option value="family-cluster">Reviewed family cluster</option>'
            '</select>'
            '<select id="safety-disposition-value" class="teaching-label-select" aria-label="Safety disposition">'
            '<option value="phishing">Phishing</option>'
            '<option value="legitimate-security">Legitimate security</option>'
            '<option value="benign-but-watch">Benign but watch</option>'
            '<option value="not-safety">Not a safety issue</option>'
            '</select>'
            '</div>'
            '<textarea id="safety-disposition-explanation" class="teaching-input" '
            'aria-label="Safety disposition explanation" '
            'placeholder="Optional note about why this belongs in the safety lane."></textarea>'
            '<div class="actions">'
            '<button type="button" class="action secondary" id="preview-safety-disposition">Preview safety disposition</button>'
            '<button type="button" class="action" id="approve-safety-disposition">Approve safety disposition</button>'
            '<button type="button" class="action secondary" id="reject-safety-disposition">Reject safety disposition</button>'
            '</div>'
            '<p class="meta">Use this when the email is scam, phishing, suspicious, or legitimate security mail. It stores a separate safety-review artifact and does not write ordinary durable classification memory.</p>'
            '</div>'
            '<div class="teaching-preview" id="teaching-preview">'
            f'<strong>Batch:</strong> {escape(batch_id)}'
            '<div class="meta">Preview results will appear here.</div>'
            '</div>'
            '<div class="teaching-preview" id="safety-preview">'
            f'<strong>Batch:</strong> {escape(batch_id)}'
            '<div class="meta">Safety review preview results will appear here.</div>'
            '</div>'
            '</div>'
            '</section>'
        )

    def _render_pending_item_card(self, batch_id: str, index: int, total_items: int, item: dict) -> str:
        preview = preview_text(item)
        active_labels = item.get("final_labels") or item.get("applied_labels") or []
        taxonomy_buttons = "".join(
            render_taxonomy_button(label_name, label_name in [gmail_label_name(label) for label in active_labels])
            for label_name in allowed_gmail_labels()
        )
        suggested = ", ".join(gmail_label_name(label) for label in item.get("applied_labels", [])) or "(none)"
        matched_rules = render_matched_teachable_rules(item)
        actionability_controls = render_actionability_controls(item)
        message_context = render_message_context(item)
        safety_priority = compute_safety_priority(item)
        safety_badges = render_safety_priority_badges(safety_priority)
        priority_card_class = " safety-priority-card" if safety_priority["priority_score"] > 0 else ""
        return (
            f'<article class="item{priority_card_class}" data-message-id="{escape(item["message_id"])}">'
            f'<div class="meta">Item {index} of {total_items}</div>'
            '<label class="teach-select">'
            f'<input type="checkbox" class="teach-example-checkbox" data-message-id="{escape(item["message_id"])}">'
            'Use as teaching example'
            '</label>'
            f'<div class="field"><strong>Batch:</strong> {escape(batch_id)}</div>'
            f'<div class="field"><strong>Message ID:</strong> {escape(item["message_id"])}</div>'
            f'<div class="field"><strong>From:</strong> {escape(item.get("sender") or "(missing)")}</div>'
            f'<div class="field"><strong>Subject:</strong> {escape(item.get("subject") or "(missing)")}</div>'
            f'<div class="field"><strong>Date:</strong> {escape(item.get("date") or "(missing)")}</div>'
            f'<div class="field"><strong>Preview:</strong> {escape(preview)}</div>'
            f'<div class="field"><strong>Suggested labels:</strong> {escape(suggested)}</div>'
            f"{safety_badges}"
            f"{matched_rules}"
            f'<div class="field"><strong>Why:</strong> {escape(item.get("interpretation") or "(missing)")}</div>'
            f"{message_context}"
            f'<div class="taxonomy">{taxonomy_buttons}</div>'
            '<p class="meta">Use Approve suggested to keep the original suggestion. '
            'Use Save selected labels after changing labels.</p>'
            f"{actionability_controls}"
            '<div class="actions">'
            '<button type="button" class="action approve">Approve suggested</button>'
            '<button type="button" class="action save secondary">Save selected labels</button>'
            '<button type="button" class="action unlabeled secondary">Mark unlabeled</button>'
            '<button type="button" class="action reject danger">Reject</button>'
            '</div>'
            '</article>'
        )

    def _default_account_id(self) -> str | None:
        if self._account_id:
            return self._account_id
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_batch(batch_path)
            account_id = batch.get("account_id")
            if account_id:
                return account_id
        return None


def serialize_item(item: dict) -> dict:
    return {
        "message_id": item["message_id"],
        "sender": item["sender"],
        "subject": item["subject"],
        "date": item["date"],
        "preview": preview_text(item),
        "snippet": item.get("snippet"),
        "body": item.get("body"),
        "interpretation": item["interpretation"],
        "suggested_labels": [gmail_label_name(label) for label in item.get("applied_labels", [])],
        "review_state": item["review_state"],
        "review_action": item["review_action"],
        "final_labels": [gmail_label_name(label) for label in item.get("final_labels") or []],
        "actionability": item.get("actionability"),
        "matched_teachable_rules": item.get("matched_teachable_rules", []),
        "decision_provenance": item.get("decision_provenance"),
    }


def _queue_item_impact_text(item: dict) -> str:
    summary = item.get("summary", {})
    item_type = item.get("item_type", "")
    if item_type == "founder-question":
        return f"about {summary.get('estimated_unblocked_messages', 0)} messages may unblock"
    if item_type == "runtime-llm-candidate":
        return f"recurring family size about {summary.get('family_count', 0)}"
    if item_type == "shadow-suggestion":
        return f"shadow family size about {summary.get('family_count', 0)}"
    if item_type == "memory-proposal":
        return f"matches about {summary.get('match_count', 0)} messages"
    if item_type == "safety-disposition":
        return f"safety match preview about {summary.get('match_count', 0)} messages"
    return "pending review"


def build_summary(items: list[dict]) -> dict:
    reviewed_items = [item for item in items if item.get("review_state") == "reviewed"]
    label_counts = Counter(
        gmail_label_name(label)
        for item in reviewed_items
        for label in item.get("final_labels") or []
    )
    return {
        "total_items": len(items),
        "reviewed_items": len(reviewed_items),
        "remaining_items": len(items) - len(reviewed_items),
        "label_counts": dict(sorted(label_counts.items())),
    }


def preview_text(item: dict) -> str:
    return item.get("snippet") or item.get("subject") or item.get("body") or "(missing)"


def render_message_context(item: dict) -> str:
    snippet = item.get("snippet")
    body = item.get("body")
    if not snippet and not body:
        return ""

    parts = []
    if snippet:
        parts.append(f'<div class="context-copy"><strong>Snippet:</strong> {escape(snippet)}</div>')
    if body:
        parts.append(f'<div class="context-copy"><strong>Body:</strong> {escape(body)}</div>')

    return '<details class="context-panel"><summary>More context</summary>' + "".join(parts) + "</details>"


def render_matched_teachable_rules(item: dict) -> str:
    rules = item.get("matched_teachable_rules") or []
    if not rules:
        return ""
    pills = "".join(
        '<span class="pill rule-match">'
        f'Matched {escape(rule.get("id", "rule"))}: {escape(rule.get("label", ""))}'
        '<span class="rule-inline-actions">'
        f'<button type="button" class="tiny-action disable-rule" data-rule-id="{escape(rule.get("id", ""))}">Disable</button>'
        '</span>'
        '</span>'
        for rule in rules
    )
    return f'<div class="field"><strong>Saved rules:</strong> {pills}</div>'


def render_safety_priority_badges(safety_priority: dict) -> str:
    if safety_priority["priority_score"] <= 0:
        return ""
    pills = [
        f'<span class="pill safety-priority">Safety priority {safety_priority["priority_score"]}</span>'
    ]
    if safety_priority["approved_disposition"]:
        pills.append(
            f'<span class="pill safety-priority">{escape(safety_priority["approved_disposition"])}</span>'
        )
    for reason in safety_priority["reasons"]:
        pills.append(f'<span class="pill safety-priority">{escape(reason)}</span>')
    return f'<div class="field"><strong>Safety:</strong> {"".join(pills)}</div>'


def render_taxonomy_button(label_name: str, is_active: bool) -> str:
    active_class = " active" if is_active else ""
    return (
        f'<button type="button" class="taxonomy-option{active_class}" '
        f'data-label="{escape(label_name)}">{escape(label_name)}</button>'
    )


def render_manual_unsubscribe_action(preview_item: dict) -> str:
    if preview_item.get("status") == "ready":
        return ""

    url = preview_item.get("url")
    if not url:
        return ""

    if url.startswith("mailto:"):
        return (
            '<div class="field"><strong>Manual action:</strong> '
            f'<a href="{escape(url)}">Manual mail unsubscribe</a></div>'
        )

    if url.startswith("https://") or url.startswith("http://"):
        return (
            '<div class="field"><strong>Manual action:</strong> '
            f'<a href="{escape(url)}" target="_blank" rel="noreferrer">Open unsubscribe link manually</a></div>'
        )

    return ""


def migrate_legacy_preference(preference: str | None) -> str | None:
    if preference == "current":
        return "reviewed"
    return preference


def render_actionability_controls(item: dict) -> str:
    if not is_plausible_inbox_removal_candidate(item):
        return ""
    selected_value = item.get("actionability") or "safe-to-remove-from-inbox"
    safe_active = " active" if selected_value == "safe-to-remove-from-inbox" else ""
    keep_active = " active" if selected_value == "keep-in-inbox" else ""
    return (
        '<div class="field"><strong>Actionability:</strong></div>'
        '<div class="actionability">'
        f'<button type="button" class="actionability-option{safe_active}" '
        'data-actionability="safe-to-remove-from-inbox">Safe to remove from inbox</button>'
        f'<button type="button" class="actionability-option{keep_active}" '
        'data-actionability="keep-in-inbox">Keep in inbox</button>'
        "</div>"
    )


def compute_safety_priority(item: dict) -> dict:
    if item.get("safety_priority"):
        return dict(item["safety_priority"])
    score = 0
    reasons = []
    approved_disposition = ""
    final_labels = set(item.get("final_labels") or [])
    applied_labels = set(item.get("applied_labels") or [])
    labels = final_labels or applied_labels
    if "account-security" in labels:
        score += 4
        reasons.append("account-security")
    approved_disposition = _approved_safety_disposition(item)
    if approved_disposition:
        score += 5
        reasons.append("approved-safety-memory")
        if approved_disposition == "phishing":
            score += 2
            reasons.append("phishing-memory")
    if _looks_suspicious_item(item):
        score += 3
        reasons.append("suspicious-signal")
    return {
        "priority_score": score,
        "reasons": reasons,
        "approved_disposition": approved_disposition,
    }


def _approved_safety_disposition(item: dict) -> str:
    if item.get("matched_approved_safety_disposition"):
        return item["matched_approved_safety_disposition"]
    provenance = item.get("decision_provenance") or {}
    retrieved_safety_keys = provenance.get("retrieved_safety_keys") or []
    if retrieved_safety_keys:
        return "approved-safety-context"
    return ""


def _looks_suspicious_item(item: dict) -> bool:
    text = f"{item.get('sender', '')} {item.get('subject', '')}".lower()
    suspicious_terms = ("verify your account", "verification code", "invoice", "payment", "package", "urgent", "service report")
    return any(term in text for term in suspicious_terms)


def _sorted_pending_items(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda item: (
            -compute_safety_priority(item)["priority_score"],
            item.get("date", ""),
            normalized_sender_email(item.get("sender")) or item.get("sender", "").lower(),
        ),
        reverse=False,
    )


def _approved_safety_contexts_for_storage(storage_dir: Path) -> list[dict]:
    store = SafetyDispositionStore(safety_dispositions_path(storage_dir))
    contexts = []
    for disposition in store.list_dispositions():
        if disposition.status != "approved":
            continue
        contexts.append(approved_safety_context(disposition))
    return contexts


def _enriched_pending_item(item: dict, safety_contexts: list[dict]) -> dict:
    enriched = dict(item)
    matched = _match_safety_context(item, safety_contexts)
    if matched:
        enriched["matched_approved_safety_disposition"] = matched["disposition"]
    enriched["safety_priority"] = compute_safety_priority(enriched)
    return enriched


def _match_safety_context(item: dict, safety_contexts: list[dict]) -> dict | None:
    sender = normalized_sender_email(item.get("sender")) or item.get("sender", "").strip().lower()
    subject = _normalized_subject(item.get("subject", ""))
    for context in safety_contexts:
        if matches_safety_context(
            {
                "sender": sender,
                "subject": subject,
                "snippet": item.get("snippet", ""),
                "body": item.get("body", ""),
            },
            context,
        ):
            return context
    return None


def _normalized_subject(subject: str) -> str:
    normalized = (subject or "").lower()
    normalized = "".join("#" if char.isdigit() else char for char in normalized)
    return " ".join(normalized.split())[:100]


def is_plausible_inbox_removal_candidate(item: dict) -> bool:
    labels = set(item.get("final_labels") or item.get("applied_labels") or [])
    return bool(labels.intersection({"promotions", "spam-low-value", "newsletter", "shopping-order", "receipt-billing"}))
