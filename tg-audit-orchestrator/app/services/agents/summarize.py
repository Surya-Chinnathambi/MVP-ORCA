"""Status summarization agent (Stage 23).

summarize_status_agent() builds a plain-language project status summary
from the scoped context snapshot. Output is an AgentDraft.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.agents.base import call_claude, log_agent_action

_SYSTEM_PROMPT = (
    "You are an audit project status reporter. Given structured project context, "
    "write a concise 3-5 sentence executive summary of the current project status. "
    "Focus on progress, open risks, and next steps. Plain text only."
)


def summarize_status_agent(
    db: Session,
    project_id: str,
    requested_by: str,
    work_mode: str = "pm",
) -> "AgentDraft":
    """Produce a plain-language status summary; return an AgentDraft."""
    import json
    from app.models.agent import AgentDraft, AgentType, DraftStatus
    from app.services.context_resolver import resolve_context

    ctx = resolve_context(db, requested_by, project_id, work_mode)
    prompt = f"Project context (JSON):\n{json.dumps(ctx, default=str)[:3000]}"

    summary = call_claude(prompt, _SYSTEM_PROMPT, max_tokens=512)

    draft = AgentDraft(
        project_id=project_id,
        agent_type=AgentType.summarize_status.value,
        status=DraftStatus.draft.value,
        requested_by=requested_by,
        payload={"summary": summary, "work_mode": work_mode, "actor_type": "agent"},
    )
    db.add(draft)
    db.flush()

    log_agent_action(
        db,
        action="agent.summarize_status",
        target_type="agent_draft",
        target_id=draft.id,
        project_id=project_id,
        requested_by=requested_by,
    )
    return draft
