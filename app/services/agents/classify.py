"""Evidence classification agent (Stage 23).

classify_evidence_agent() reads an EvidenceItem's extracted text,
calls Claude Haiku to suggest a pack-category label, and stores the
result as an AgentDraft. It never writes to EvidenceItem.classification
directly — that requires human acceptance.

Guardrails enforced:
  - Restricted evidence requires the requesting user to hold evidence_item permission.
  - Output is always status=draft; classification is not applied until accepted.
  - Action is logged with actor_type=agent.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.services.agents.base import (
    AgentGuardError,
    assert_evidence_access,
    call_claude,
    log_agent_action,
)

_SYSTEM_PROMPT = (
    "You are an audit evidence classification assistant. "
    "Given a text excerpt from an audit evidence document and a list of "
    "audit control categories, respond with ONLY the single best-matching "
    "category label from the provided list. No explanation."
)

_DEFAULT_CATEGORIES = [
    "access_control", "data_protection", "network_security", "audit_logging",
    "incident_response", "policy_documentation", "risk_management",
    "vulnerability_management", "encryption", "physical_security",
    "third_party_risk", "business_continuity", "compliance", "other",
]


def classify_evidence_agent(
    db: Session,
    evidence_item_id: str,
    requested_by: str,
    categories: Optional[list[str]] = None,
) -> "AgentDraft":
    """Classify evidence text into a pack category; return an AgentDraft.

    Args:
        db: SQLAlchemy session.
        evidence_item_id: ID of the EvidenceItem to classify.
        requested_by: User ID requesting the classification.
        categories: Override category list (defaults to _DEFAULT_CATEGORIES).
    """
    from app.models.agent import AgentDraft, AgentType, DraftStatus
    from app.models.evidence import EvidenceItem

    item = db.get(EvidenceItem, evidence_item_id)
    if item is None:
        raise ValueError(f"EvidenceItem {evidence_item_id!r} not found")

    assert_evidence_access(db, item, requested_by)

    cats = categories or _DEFAULT_CATEGORIES
    text_snippet = (item.extracted_text or "")[:2000]

    prompt = (
        f"Evidence text (first 2000 chars):\n{text_snippet}\n\n"
        f"Categories: {', '.join(cats)}\n\n"
        "Which single category best matches this evidence?"
    )

    suggested = call_claude(prompt, _SYSTEM_PROMPT, max_tokens=64)
    # Normalise to lowercase, trim whitespace; fall back to "other" if unrecognised
    suggested_clean = suggested.lower().strip().rstrip(".")
    if suggested_clean not in [c.lower() for c in cats]:
        suggested_clean = "other"

    draft = AgentDraft(
        project_id=item.project_id,
        agent_type=AgentType.classify_evidence.value,
        status=DraftStatus.draft.value,
        requested_by=requested_by,
        payload={
            "evidence_item_id": evidence_item_id,
            "suggested_classification": suggested_clean,
            "categories_used": cats,
            "actor_type": "agent",
        },
    )
    db.add(draft)
    db.flush()

    log_agent_action(
        db,
        action="agent.classify_evidence",
        target_type="evidence_item",
        target_id=evidence_item_id,
        project_id=item.project_id,
        requested_by=requested_by,
        after={"suggested_classification": suggested_clean, "draft_id": draft.id},
    )
    return draft
