"""EngagementObjective service — dependency resolution, cycle detection, acceptance criteria.

Stage 17 full implementation.  Service is intentionally service-neutral: no
VAPT/offensive concepts live here (those belong in the VAPT pack).
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.engagement import EngagementObjective


# ── Topological sort + cycle detection ───────────────────────────────────────

def topological_sort(objectives: list[EngagementObjective]) -> list[EngagementObjective]:
    """Return objectives sorted so every prerequisite appears before its dependant.

    Raises ValueError if a cycle is detected.
    """
    id_to_obj: dict[str, EngagementObjective] = {o.id: o for o in objectives}
    visited: set[str] = set()
    in_stack: set[str] = set()
    result: list[EngagementObjective] = []

    def visit(oid: str) -> None:
        if oid in in_stack:
            raise ValueError(f"Dependency cycle detected involving objective {oid!r}")
        if oid in visited:
            return
        in_stack.add(oid)
        for dep_id in (id_to_obj[oid].depends_on or []):
            if dep_id in id_to_obj:
                visit(dep_id)
        in_stack.discard(oid)
        visited.add(oid)
        result.append(id_to_obj[oid])

    for obj in objectives:
        if obj.id not in visited:
            visit(obj.id)
    return result


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def create_objective(
    db: Session,
    *,
    project_id: str,
    title: str,
    description: Optional[str] = None,
    acceptance_criteria: Optional[str] = None,
    depends_on: Optional[list] = None,
    linked_requirement_ids: Optional[list] = None,
    linked_evidence_ids: Optional[list] = None,
) -> EngagementObjective:
    obj = EngagementObjective(
        project_id=project_id,
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        depends_on=depends_on or [],
        status="open",
        linked_requirement_ids=linked_requirement_ids or [],
        linked_evidence_ids=linked_evidence_ids or [],
    )
    db.add(obj)
    return obj


def list_objectives(db: Session, project_id: str) -> list[EngagementObjective]:
    return db.query(EngagementObjective).filter_by(project_id=project_id).all()


# ── Link helpers (objectives ↔ requirements ↔ evidence) ──────────────────────

def link_requirement(db: Session, objective_id: str, requirement_id: str) -> EngagementObjective:
    """Append requirement_id to objective's linked_requirement_ids (idempotent)."""
    obj = _get_or_raise(db, objective_id)
    ids = list(obj.linked_requirement_ids or [])
    if requirement_id not in ids:
        ids.append(requirement_id)
        obj.linked_requirement_ids = ids
    return obj


def link_evidence(db: Session, objective_id: str, evidence_item_id: str) -> EngagementObjective:
    """Append evidence_item_id to objective's linked_evidence_ids (idempotent).

    An evidence item may serve multiple objectives — no uniqueness restriction here.
    """
    obj = _get_or_raise(db, objective_id)
    ids = list(obj.linked_evidence_ids or [])
    if evidence_item_id not in ids:
        ids.append(evidence_item_id)
        obj.linked_evidence_ids = ids
    return obj


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def complete_objective(db: Session, objective_id: str) -> EngagementObjective:
    """Mark an objective complete, enforcing prerequisites and acceptance criteria.

    Rules:
    1. All depends_on objectives must already be ``complete``.
    2. If acceptance_criteria is set, the objective must have at least one
       linked evidence item or linked requirement to satisfy it.

    Raises ValueError on any violation.
    """
    obj = _get_or_raise(db, objective_id)

    # 1. Prerequisite check
    for dep_id in (obj.depends_on or []):
        dep = db.get(EngagementObjective, dep_id)
        if dep is None or dep.status != "complete":
            raise ValueError(
                f"Prerequisite objective {dep_id!r} is not complete; "
                f"cannot complete {objective_id!r}"
            )

    # 2. Acceptance-criteria check
    if obj.acceptance_criteria:
        if not (obj.linked_evidence_ids or obj.linked_requirement_ids):
            raise ValueError(
                f"Objective {objective_id!r} has acceptance_criteria "
                "but no linked evidence or requirements to satisfy it"
            )

    obj.status = "complete"
    return obj


def sorted_plan(db: Session, project_id: str) -> list[EngagementObjective]:
    """Return all project objectives in dependency order."""
    objectives = list_objectives(db, project_id)
    return topological_sort(objectives)


# ── Private ───────────────────────────────────────────────────────────────────

def _get_or_raise(db: Session, objective_id: str) -> EngagementObjective:
    obj = db.get(EngagementObjective, objective_id)
    if obj is None:
        raise ValueError(f"EngagementObjective {objective_id!r} not found")
    return obj
