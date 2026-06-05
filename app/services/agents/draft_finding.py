"""Draft-finding agent (Stage 23).

draft_finding_agent() uses scoped project context (analyst work mode) to
suggest a finding draft. Output is an AgentDraft with status=draft.

GUARDRAILS:
  - suggested_severity is present in the draft payload (the human decides whether to adopt it)
    but the agent NEVER calls Finding.severity = ... — no severity is committed.
  - Agent action logged with actor_type=agent.
  - Agent cannot approve — agent_decide_approval raises AgentGuardError if called.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.services.agents.base import call_claude, log_agent_action

_SYSTEM_PROMPT = (
    "You are a security audit assistant. Given a project context summary and "
    "a short description, draft a concise audit finding. "
    "Respond with a JSON object with keys: title, description, suggested_severity "
    "(one of: critical, high, medium, low, informational), rationale. "
    "Do not include any other text outside the JSON."
)


def draft_finding_agent(
    db: Session,
    project_id: str,
    title_hint: str,
    description: str,
    requested_by: str,
) -> "AgentDraft":
    """Draft a finding suggestion; return an AgentDraft with status=draft.

    The draft's suggested_severity is advisory only — the agent never sets
    Finding.severity. A human must accept and set severity via the normal workflow.
    """
    import json
    from app.models.agent import AgentDraft, AgentType, DraftStatus

    # Get a scoped context snapshot for analyst work mode
    context_summary = _build_context_summary(db, project_id, requested_by)

    prompt = (
        f"Project context:\n{context_summary}\n\n"
        f"Finding description:\nTitle hint: {title_hint}\n{description}\n\n"
        "Produce the JSON finding draft."
    )

    raw = call_claude(prompt, _SYSTEM_PROMPT, max_tokens=512)

    # Parse JSON; fall back to a minimal structure on failure
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {
            "title": title_hint,
            "description": description,
            "suggested_severity": None,
            "rationale": raw,
        }

    # Strip keys that would allow the agent to confirm/set severity on a real Finding
    # The payload carries the suggestion only — no Finding row is created
    draft_payload = {
        "title": parsed.get("title", title_hint),
        "description": parsed.get("description", description),
        "suggested_severity": parsed.get("suggested_severity"),
        "rationale": parsed.get("rationale", ""),
        "status": "draft",
        "actor_type": "agent",
        # Explicitly mark that severity is NOT confirmed
        "severity_confirmed": False,
    }

    draft = AgentDraft(
        project_id=project_id,
        agent_type=AgentType.draft_finding.value,
        status=DraftStatus.draft.value,
        requested_by=requested_by,
        payload=draft_payload,
    )
    db.add(draft)
    db.flush()

    log_agent_action(
        db,
        action="agent.draft_finding",
        target_type="agent_draft",
        target_id=draft.id,
        project_id=project_id,
        requested_by=requested_by,
        after={"draft_id": draft.id, "title": draft_payload["title"]},
    )
    return draft


def _build_context_summary(db: Session, project_id: str, user_id: str) -> str:
    """Return a short text summary of the project context for the analyst mode."""
    try:
        from app.services.context_resolver import resolve_context
        ctx = resolve_context(db, user_id, project_id, "analyst")
        lines = [f"Phase: {ctx.get('phase', 'unknown')}"]
        progress = ctx.get("progress", {})
        if progress:
            lines.append(f"Tasks: {progress.get('tasks', {})}")
            lines.append(f"Findings: {progress.get('findings', {})}")
        return "\n".join(lines)
    except Exception:
        return f"Project {project_id}"
