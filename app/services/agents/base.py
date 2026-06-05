"""Agent base layer — guardrails, logging, and Claude API wrapper (Stage 23).

GUARDRAILS (enforced in code, not prompt-only):
  - Agents cannot approve ApprovalRequests → agent_decide_approval raises AgentGuardError
  - Agents cannot confirm/set finding severity → agent_set_severity raises AgentGuardError
  - Agents cannot release reports → agent_release_report raises AgentGuardError
  - Agents cannot access restricted evidence without the requesting user's permission

Every agent action writes an AuditTrailEvent with after={"actor_type": "agent"}.
actor_id is set to None (agents have no user account); requested_by is stored in after.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session


class AgentGuardError(Exception):
    """Raised when an agent attempts a forbidden action."""


# ── Guardrail stubs ───────────────────────────────────────────────────────────

def agent_decide_approval(*args, **kwargs) -> None:
    """Agents cannot approve ApprovalRequests. Always raises AgentGuardError."""
    raise AgentGuardError(
        "Agents cannot approve ApprovalRequests. Human approval is required."
    )


def agent_set_severity(*args, **kwargs) -> None:
    """Agents cannot confirm or set finding severity. Always raises AgentGuardError."""
    raise AgentGuardError(
        "Agents cannot set or confirm finding severity. A human reviewer must decide."
    )


def agent_release_report(*args, **kwargs) -> None:
    """Agents cannot release reports. Always raises AgentGuardError."""
    raise AgentGuardError(
        "Agents cannot release reports. Report release requires human approval."
    )


# ── Audit logging ─────────────────────────────────────────────────────────────

def log_agent_action(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: str,
    project_id: Optional[str] = None,
    requested_by: Optional[str] = None,
    after: Optional[dict] = None,
) -> None:
    """Write an AuditTrailEvent tagged actor_type=agent (actor_id=None)."""
    from app.services.audit import record_event
    payload = {"actor_type": "agent"}
    if requested_by:
        payload["requested_by"] = requested_by
    if after:
        payload.update(after)
    record_event(
        db,
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_id=None,
        project_id=project_id,
        after=payload,
    )


# ── Evidence access guard ─────────────────────────────────────────────────────

def assert_evidence_access(db: Session, item, user_id: str) -> None:
    """Raise AgentGuardError if the requesting user cannot access a restricted item."""
    if not getattr(item, "is_restricted", False):
        return
    from app.models.users import User
    user = db.get(User, user_id)
    if user is None:
        raise AgentGuardError(f"User {user_id!r} not found")
    from app.deps import check_evidence_access
    if not check_evidence_access(item, user, db):
        raise AgentGuardError(
            f"Agent cannot access restricted evidence item {item.id!r} on behalf of user {user_id!r}"
        )


# ── Claude API wrapper ────────────────────────────────────────────────────────

def call_claude(prompt: str, system: str, max_tokens: int = 512) -> str:
    """Call Claude Haiku and return the text response.

    API key comes from settings.claude_api_key (.env only).
    Raises if the key is not set.
    """
    from app.config import settings
    if not settings.claude_api_key:
        raise AgentGuardError("CLAUDE_API_KEY is not configured — cannot call AI agent")
    from anthropic import Anthropic
    client = Anthropic(api_key=settings.claude_api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()
