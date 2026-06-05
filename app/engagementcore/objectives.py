"""EngagementObjective service — thin stub for Stage 14.

Full dependency resolution, cycle detection, and acceptance-criteria
enforcement are implemented in Stage 17.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.engagement import EngagementObjective


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


def complete_objective(db: Session, objective_id: str) -> EngagementObjective:
    """Mark objective complete. Full prerequisite enforcement added in Stage 17."""
    obj = db.get(EngagementObjective, objective_id)
    if obj is None:
        raise ValueError(f"Objective {objective_id!r} not found")
    obj.status = "complete"
    return obj
